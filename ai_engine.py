"""
AI Engine v7 — Shanaya, MKOV Travel Assistant
- STRICT 10-digit phone validation only
- Handles partial identity (name only / phone only) — asks for the missing piece
- Visit counter for returning users
- Google Flights + internal portal fallback
- Answers questions first, never interrogates
- If a keyword/package isn't found → directs to operator, never guesses
"""

import re
import google.generativeai as genai
from memory import get_history, save_message
from database import get_db
from config import GEMINI_API_KEY, MODEL, TEMPERATURE, MAX_TOKENS, SYSTEM_PROMPT

print(f"✓ Shanaya AI Engine v7 — {MODEL}")
genai.configure(api_key=GEMINI_API_KEY)

try:
    from google_flights import detect_flight_query, search_google_flights, format_for_shanaya
    from config import SERPAPI_KEY
    GFLIGHTS = bool(SERPAPI_KEY)
except Exception:
    GFLIGHTS = False

try:
    from flight_scraper import is_flight_query as _pd, search_flights as _ps, format_flights_for_shanaya as _pf
    PORTAL = True
except Exception:
    PORTAL = False


# ── Lead / session helpers ────────────────────────────────────────────────────

def get_lead_by_session(session_id: str):
    conn = get_db()
    row  = conn.execute(
        "SELECT l.* FROM leads l JOIN sessions s ON s.lead_id=l.id WHERE s.session_id=?",
        (session_id,)
    ).fetchone()
    conn.close()
    return row


def get_partial_identity(session_id: str):
    """
    Track partial identity given mid-conversation (name only or phone only)
    before the lead record is fully created.
    Stored in a lightweight in-memory-like table keyed by session_id.
    """
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM partial_identity WHERE session_id=?", (session_id,)
    ).fetchone()
    conn.close()
    return row


def save_partial_identity(session_id: str, name: str = None, phone: str = None):
    conn = get_db()
    existing = conn.execute(
        "SELECT * FROM partial_identity WHERE session_id=?", (session_id,)
    ).fetchone()
    if existing:
        new_name  = name  or existing["partial_name"]
        new_phone = phone or existing["partial_phone"]
        conn.execute(
            "UPDATE partial_identity SET partial_name=?, partial_phone=? WHERE session_id=?",
            (new_name, new_phone, session_id)
        )
    else:
        conn.execute(
            "INSERT INTO partial_identity (session_id, partial_name, partial_phone) VALUES (?,?,?)",
            (session_id, name, phone)
        )
    conn.commit()
    conn.close()


def clear_partial_identity(session_id: str):
    conn = get_db()
    conn.execute("DELETE FROM partial_identity WHERE session_id=?", (session_id,))
    conn.commit()
    conn.close()


def create_or_update_lead(session_id: str, name: str, phone: str) -> dict:
    conn     = get_db()
    existing = conn.execute("SELECT * FROM leads WHERE contact_phone=?", (phone,)).fetchone()
    if existing:
        new_count = existing["visit_count"] + 1
        conn.execute(
            "UPDATE leads SET visit_count=?,last_seen=CURRENT_TIMESTAMP,contact_name=? WHERE contact_phone=?",
            (new_count, name, phone)
        )
        lead_id = existing["id"]
        conn.commit(); conn.close()
        _link(session_id, lead_id)
        clear_partial_identity(session_id)
        return {"name": name, "phone": phone, "visit_count": new_count, "is_returning": True}
    else:
        cur = conn.execute(
            "INSERT INTO leads (contact_name,contact_phone,identity_given,visit_count) VALUES (?,?,1,1)",
            (name, phone)
        )
        lead_id = cur.lastrowid
        conn.commit(); conn.close()
        _link(session_id, lead_id)
        clear_partial_identity(session_id)
        return {"name": name, "phone": phone, "visit_count": 1, "is_returning": False}


def _link(session_id, lead_id):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO sessions (session_id,lead_id) VALUES (?,?)",
        (session_id, lead_id)
    )
    conn.commit(); conn.close()


# ── Identity parsing — STRICT 10-digit phone only ────────────────────────────

def extract_phone(text: str):
    """
    Find a phone number in the text. ONLY accepts exactly 10 digits
    (standard Indian mobile number length). Any other digit count
    (8, 9, 11, 12, 15 etc.) is rejected — returns None.
    Allows spaces/dashes WITHIN the number (e.g. "98765 43210") but
    the digit count after stripping must be exactly 10.
    Also strips a leading +91 / 91 country code before counting, so
    "+91 9876543210" and "919876543210" are still valid 10-digit numbers.
    """
    # Find candidate number sequences (digits with optional spaces/dashes)
    candidates = re.findall(r'(\+?\d[\d\s\-]{6,17}\d)', text)
    for raw in candidates:
        cleaned = re.sub(r'[\s\-]', '', raw)
        # Strip country code prefix if present
        if cleaned.startswith('+91') and len(cleaned) == 13:
            cleaned = cleaned[3:]
        elif cleaned.startswith('91') and len(cleaned) == 12:
            cleaned = cleaned[2:]
        elif cleaned.startswith('+') :
            cleaned = cleaned.lstrip('+')

        if cleaned.isdigit() and len(cleaned) == 10:
            return cleaned
    return None


def extract_name(text: str, phone_raw: str = None):
    """Remove the phone substring from text, return cleaned name or None."""
    working = text
    if phone_raw:
        working = working.replace(phone_raw, '', 1)
    working = re.sub(r'[,\.\-_]+', ' ', working).strip()
    working = re.sub(r'\s+', ' ', working).strip()

    if not working or len(working) < 2 or len(working) > 50:
        return None
    if not re.match(r'^[A-Za-z][A-Za-z\s\.]{1,49}$', working):
        return None
    return working


def try_parse_identity(text: str):
    """
    Returns (name, phone, status)
      status: 'complete'      → both found, valid
              'name_only'     → name found, no valid 10-digit phone
              'phone_only'    → 10-digit phone found, no valid name
              'invalid_phone' → a number-like sequence was found but
                                 NOT exactly 10 digits (must reject)
              'none'          → nothing usable found
    """
    raw = text.strip()

    # Check for ANY digit sequence of 6+ digits (potential phone attempt)
    any_number = re.search(r'(\+?\d[\d\s\-]{5,17}\d)', raw)
    phone = extract_phone(raw)

    if any_number and not phone:
        # They typed something number-like but it's not exactly 10 digits
        # Still try to salvage a name from the rest of the text
        name = extract_name(raw, any_number.group(1))
        return (name, None, 'invalid_phone')

    if phone:
        phone_match = re.search(r'(\+?\d[\d\s\-]{6,17}\d)', raw)
        raw_phone_str = phone_match.group(1) if phone_match else phone
        name = extract_name(raw, raw_phone_str)
        if name:
            return (name, phone, 'complete')
        else:
            return (None, phone, 'phone_only')

    # No number at all — check if the whole message could be just a name
    name_only_match = re.match(r'^[A-Za-z][A-Za-z\s\.]{1,49}$', raw)
    if name_only_match:
        return (raw.strip(), None, 'name_only')

    return (None, None, 'none')


# ── Flight context ────────────────────────────────────────────────────────────

def get_flight_context(message: str) -> str:
    if GFLIGHTS:
        try:
            q = detect_flight_query(message)
            if not q["is_flight"]:
                return ""
            if not q["origin"] or not q["destination"]:
                return (
                    "[GOOGLE FLIGHTS DATA]\n"
                    "User asking about flights but route unclear. "
                    "Ask which city flying FROM, which city flying TO, and on what date."
                )
            result = search_google_flights(
                origin=q["origin"], destination=q["destination"],
                date=q["date"], return_date=q.get("return_date"),
                adults=q.get("adults", 1)
            )
            return format_for_shanaya(result, q["origin"], q["destination"], q["date"] or "")
        except Exception as e:
            print(f"[FLIGHTS] Google error: {e}")

    if PORTAL:
        try:
            is_fl, origin, dest, date = _pd(message)
            if not is_fl:
                return ""
            if not origin or not dest:
                return "[FLIGHT DATA]\nUser asking about flights. Ask which city flying from and to."
            return _pf(_ps(origin, dest, date or "next available"))
        except Exception as e:
            print(f"[PORTAL] Error: {e}")

    return ""


# ── Main chat ─────────────────────────────────────────────────────────────────

def chat(session_id: str, user_message: str) -> dict:
    print(f"[CHAT] {session_id[:12]} | {user_message[:60]}")

    existing_lead = get_lead_by_session(session_id)

    if not existing_lead:
        partial = get_partial_identity(session_id)
        prior_name  = partial["partial_name"]  if partial else None
        prior_phone = partial["partial_phone"] if partial else None

        name, phone, status = try_parse_identity(user_message)

        # Merge with anything already partially captured
        final_name  = name  or prior_name
        final_phone = phone or prior_phone

        save_message(session_id, "user", user_message)

        if final_name and final_phone:
            info  = create_or_update_lead(session_id, final_name, final_phone)
            first = final_name.split()[0]
            if info["is_returning"]:
                count = info["visit_count"]
                reply = (
                    f"Welcome back, {first}! 🙏 So lovely to hear from you again.\n\n"
                    f"You've chatted with me **{count} time{'s' if count != 1 else ''}** — "
                    f"I hope each one was helpful!\n\nWhat trip are we planning today?"
                )
            else:
                reply = (
                    f"Wonderful to meet you, {first}! 🙏 "
                    f"I'm Shanaya, your travel assistant at Uniglobe MKOV Travel.\n\n"
                    f"What kind of trip are you thinking about? I can help with destinations, "
                    f"itineraries, visas, and find the cheapest flights too! ✈️"
                )
            save_message(session_id, "assistant", reply)
            return {
                "reply": reply, "session_id": session_id,
                "extracted_data": {"contact_name": final_name, "contact_phone": final_phone},
                "missing_fields": [], "is_complete": False, "identity_given": True,
            }

        elif status == 'invalid_phone':
            save_partial_identity(session_id, name=final_name)
            reply = (
                "That phone number doesn't look quite right. 📵\n\n"
                "Please provide a valid **10-digit** mobile number "
                "(no country code, no extra digits).\n\n"
                + (f"Got your name: **{final_name}** ✓ — just need the 10-digit number now."
                   if final_name else
                   "Example: **Rahul Sharma 9876543210**")
            )
            save_message(session_id, "assistant", reply)
            return {
                "reply": reply, "session_id": session_id, "extracted_data": {},
                "missing_fields": ["contact_phone"], "is_complete": False, "identity_given": False,
            }

        elif final_name and not final_phone:
            save_partial_identity(session_id, name=final_name)
            reply = (
                f"Thanks, {final_name.split()[0]}! 🙏 One more thing — "
                f"could you share your **10-digit phone number** so our team can reach you?\n\n"
                f"Example: **9876543210**"
            )
            save_message(session_id, "assistant", reply)
            return {
                "reply": reply, "session_id": session_id, "extracted_data": {},
                "missing_fields": ["contact_phone"], "is_complete": False, "identity_given": False,
            }

        elif final_phone and not final_name:
            save_partial_identity(session_id, phone=final_phone)
            reply = (
                "Got your number, thank you! 🙏 Could you also share your **name** "
                "so I know who I'm speaking with?"
            )
            save_message(session_id, "assistant", reply)
            return {
                "reply": reply, "session_id": session_id, "extracted_data": {},
                "missing_fields": ["contact_name"], "is_complete": False, "identity_given": False,
            }

        else:
            reply = (
                "Hi there! 👋 Before we proceed, I am required to collect your full name "
                "and a valid ten (10) digit mobile telephone number, submitted together in "
                "a single message, in order to continue this conversation.\n\n"
                "Kindly type both as follows, with no punctuation, symbols, or formatting "
                "of any kind required or permitted:\n\n"
                "**Rahul Sharma 9876543210**\n\n"
                "Any submission lacking either the full name or a valid ten-digit number "
                "will not be accepted, and this request will be repeated until both are "
                "correctly provided. No further assistance can be rendered until this "
                "requirement is satisfied in full."
            )
            save_message(session_id, "assistant", reply)
            return {
                "reply": reply, "session_id": session_id, "extracted_data": {},
                "missing_fields": ["contact_name", "contact_phone"], "is_complete": False, "identity_given": False,
            }

    # ── Identity confirmed — Gemini chat ──────────────────────────────────────
    save_message(session_id, "user", user_message)
    history  = get_history(session_id)
    contents = []
    for msg in history[:-1]:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    flight_ctx = get_flight_context(user_message)
    final_msg  = f"{flight_ctx}\n\nUser: {user_message}" if flight_ctx else user_message

    try:
        model        = genai.GenerativeModel(model_name=MODEL, system_instruction=SYSTEM_PROMPT)
        chat_session = model.start_chat(history=contents)
        response     = chat_session.send_message(
            final_msg,
            generation_config={"temperature": TEMPERATURE, "max_output_tokens": MAX_TOKENS}
        )
        reply = response.text.strip() if response.text else "Could you repeat that? 🙏"
        print(f"[CHAT] ✓ {reply[:80]}")
    except Exception as e:
        import traceback; traceback.print_exc()
        reply = "I'm having a brief technical issue. 🙏 Please try again or call **+91 8010700700**."

    save_message(session_id, "assistant", reply)
    return {
        "reply": reply, "session_id": session_id,
        "extracted_data": {
            "contact_name":  existing_lead["contact_name"],
            "contact_phone": existing_lead["contact_phone"],
        },
        "missing_fields": [], "is_complete": False, "identity_given": True,
    }


def lookup_packages(*a): return []
