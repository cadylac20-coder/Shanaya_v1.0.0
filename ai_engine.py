"""
AI Engine — Shanaya, MKOV Travel Assistant
- STRICT 10-digit phone validation only
- Partial identity handling: if only name OR only phone given, ask for
  the specific missing piece and remember what was already provided
- Visit counter for returning users
- Google Flights + internal portal fallback
- Never invents info: unknown destinations/packages → redirect to agent
"""

import re
import google.generativeai as genai
from memory import get_history, save_message
from database import get_db
from config import GEMINI_API_KEY, MODEL, TEMPERATURE, MAX_TOKENS, SYSTEM_PROMPT, OPERATOR_PHONE

print(f"✓ Shanaya AI Engine — {MODEL}")
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
        return {"name": name, "phone": phone, "visit_count": new_count, "is_returning": True}
    else:
        cur = conn.execute(
            "INSERT INTO leads (contact_name,contact_phone,identity_given,visit_count) VALUES (?,?,1,1)",
            (name, phone)
        )
        lead_id = cur.lastrowid
        conn.commit(); conn.close()
        _link(session_id, lead_id)
        return {"name": name, "phone": phone, "visit_count": 1, "is_returning": False}


def _link(session_id, lead_id):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO sessions (session_id,lead_id) VALUES (?,?)",
        (session_id, lead_id)
    )
    conn.commit(); conn.close()


# ── Pending (partial) identity helpers ────────────────────────────────────────

def get_pending(session_id: str):
    conn = get_db()
    row  = conn.execute(
        "SELECT name, phone FROM pending_identity WHERE session_id=?", (session_id,)
    ).fetchone()
    conn.close()
    return {"name": row["name"], "phone": row["phone"]} if row else {"name": None, "phone": None}


def save_pending(session_id: str, name=None, phone=None):
    existing = get_pending(session_id)
    final_name  = name  or existing["name"]
    final_phone = phone or existing["phone"]
    conn = get_db()
    conn.execute(
        """INSERT INTO pending_identity (session_id, name, phone, updated_at)
           VALUES (?,?,?,CURRENT_TIMESTAMP)
           ON CONFLICT(session_id) DO UPDATE SET
             name=excluded.name, phone=excluded.phone, updated_at=CURRENT_TIMESTAMP""",
        (session_id, final_name, final_phone)
    )
    conn.commit(); conn.close()
    return {"name": final_name, "phone": final_phone}


def clear_pending(session_id: str):
    conn = get_db()
    conn.execute("DELETE FROM pending_identity WHERE session_id=?", (session_id,))
    conn.commit(); conn.close()


# ── STRICT identity extraction — phone MUST be exactly 10 digits ─────────────

def extract_phone(text: str):
    """
    Find a phone number in the text. Only accepts EXACTLY 10 digits
    (after stripping spaces/dashes, and after stripping a leading
    country code like +91 or 91 if present). Any other digit length
    is rejected — returns None.
    """
    # Find all digit runs (allowing spaces/dashes within a run)
    candidates = re.findall(r'(\+?\d[\d\s\-]{6,16}\d)', text)
    for raw in candidates:
        cleaned = re.sub(r'[\s\-]', '', raw)
        # Strip leading + and country code 91 if present
        digits = cleaned.lstrip('+')
        if digits.startswith('91') and len(digits) == 12:
            digits = digits[2:]
        if digits.isdigit() and len(digits) == 10:
            return digits
    return None


def extract_name(text: str, phone_raw_matches: list = None):
    """
    Extract a plausible name from text after removing any phone-like digit runs.
    """
    cleaned = re.sub(r'(\+?\d[\d\s\-]{6,16}\d)', ' ', text)
    cleaned = re.sub(r'[,\.\-_]+', ' ', cleaned).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if not cleaned or len(cleaned) < 2 or len(cleaned) > 50:
        return None
    if not re.match(r'^[A-Za-z][A-Za-z\s\.]{1,49}$', cleaned):
        return None
    return cleaned


IDENTITY_PROMPT = (
    "Hi there! 👋 Before we can continue, I need TWO things from you, "
    "sent together in ONE message:\n\n"
    "1️⃣ Your full name\n"
    "2️⃣ Your phone number — it must be exactly 10 digits, numbers only "
    "(no country code, no +91, no spaces, no dashes)\n\n"
    "**Example — copy this format exactly:**\n"
    "Rahul Sharma 9876543210\n\n"
    "That is the ONLY format required. Please type your name, followed by "
    "your 10-digit phone number, exactly like the example above, and send it "
    "as a single message."
)


def chat(session_id: str, user_message: str) -> dict:
    print(f"[CHAT] {session_id[:12]} | {user_message[:60]}")

    existing_lead = get_lead_by_session(session_id)

    if not existing_lead:
        pending = get_pending(session_id)

        phone_found = extract_phone(user_message)
        name_found  = extract_name(user_message)

        final_name  = name_found  or pending["name"]
        final_phone = phone_found or pending["phone"]

        # ── Both present — complete the identity gate ─────────────────────────
        if final_name and final_phone:
            clear_pending(session_id)
            info  = create_or_update_lead(session_id, final_name, final_phone)
            save_message(session_id, "user", user_message)
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

        # ── Only phone given so far — ask specifically for name ───────────────
        if final_phone and not final_name:
            save_pending(session_id, phone=final_phone)
            save_message(session_id, "user", user_message)
            reply = (
                f"Got your number ✅ ({final_phone}). "
                f"Now please also send me your **full name** so I can address you properly.\n\n"
                f"Just reply with your name — nothing else needed."
            )
            save_message(session_id, "assistant", reply)
            return {
                "reply": reply, "session_id": session_id,
                "extracted_data": {}, "missing_fields": ["contact_name"],
                "is_complete": False, "identity_given": False,
            }

        # ── Only name given so far — ask specifically for phone ───────────────
        if final_name and not final_phone:
            save_pending(session_id, name=final_name)
            save_message(session_id, "user", user_message)
            first = final_name.split()[0]
            reply = (
                f"Thanks, {first}! ✅ Now I just need your **phone number** — "
                f"it must be exactly 10 digits, numbers only (no country code, "
                f"no +91, no spaces or dashes).\n\n"
                f"Example: 9876543210"
            )
            save_message(session_id, "assistant", reply)
            return {
                "reply": reply, "session_id": session_id,
                "extracted_data": {}, "missing_fields": ["contact_phone"],
                "is_complete": False, "identity_given": False,
            }

        # ── Neither found — full explicit instructions ─────────────────────────
        save_message(session_id, "user", user_message)
        save_message(session_id, "assistant", IDENTITY_PROMPT)
        return {
            "reply": IDENTITY_PROMPT, "session_id": session_id,
            "extracted_data": {}, "missing_fields": ["contact_name", "contact_phone"],
            "is_complete": False, "identity_given": False,
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
        reply = f"I'm having a brief technical issue. 🙏 Please try again or call **{OPERATOR_PHONE}**."

    save_message(session_id, "assistant", reply)
    return {
        "reply": reply, "session_id": session_id,
        "extracted_data": {
            "contact_name":  existing_lead["contact_name"],
            "contact_phone": existing_lead["contact_phone"],
        },
        "missing_fields": [], "is_complete": False, "identity_given": True,
    }


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
                    "Ask which city flying FROM, which city TO, and on what date."
                )
            result = search_google_flights(
                origin=q["origin"], destination=q["destination"],
                date=q["date"], return_date=q.get("return_date"), adults=q.get("adults",1)
            )
            return format_for_shanaya(result, q["origin"], q["destination"], q["date"] or "")
        except Exception as e:
            print(f"[FLIGHTS] Error: {e}")

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


def lookup_packages(*a): return []
