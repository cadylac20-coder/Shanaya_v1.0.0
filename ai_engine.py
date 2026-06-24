"""
AI Engine v6 Final — Shanaya, MKOV Travel Assistant
- Lax name+phone parser (no comma needed)
- Returns contact_phone in extracted_data so widget stores it in localStorage
- Visit counter for returning users
- Google Flights + internal portal fallback
- Answers questions first, never interrogates
"""

import re
import google.generativeai as genai
from memory import get_history, save_message
from database import get_db
from config import GEMINI_API_KEY, MODEL, TEMPERATURE, MAX_TOKENS, SYSTEM_PROMPT

print(f"✓ Shanaya AI Engine v6 Final — {MODEL}")
genai.configure(api_key=GEMINI_API_KEY)

try:
    from google_flights import detect_flight_query, search_google_flights, format_for_shanaya
    from config import SERPAPI_KEY
    GFLIGHTS = bool(SERPAPI_KEY)
    print(f"✓ Google Flights: {'enabled' if GFLIGHTS else 'disabled (no SERPAPI_KEY)'}")
except Exception as e:
    GFLIGHTS = False
    print(f"⚠ Google Flights not loaded: {e}")

try:
    from flight_scraper import is_flight_query as _pd, search_flights as _ps, format_flights_for_shanaya as _pf
    PORTAL = True
    print("✓ Internal flight portal loaded")
except Exception as e:
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


def try_parse_identity(text: str):
    """
    Lax name + phone parser. Accepts:
      Rahul Sharma 9876543210
      Rahul Sharma, 9876543210
      9876543210 Rahul Sharma
      rahul 98765 43210
      RahulSharma9876543210
    Logic:
      1. Find phone = longest digit sequence (with optional spaces/dashes) that is 8-15 digits
      2. Everything else = name (must be 2-50 chars, letters and spaces only)
    """
    raw = text.strip()

    # Find phone number — digits possibly separated by spaces or dashes
    phone_match = re.search(r'(\+?[\d][\d\s\-]{6,18}[\d])', raw)
    if not phone_match:
        return None, None

    phone_raw   = phone_match.group(1)
    phone_clean = re.sub(r'[\s\-]', '', phone_raw)

    if not phone_clean.isdigit() or not (8 <= len(phone_clean) <= 15):
        return None, None

    # Remove phone from text to get name
    name_part = raw.replace(phone_raw, '', 1).strip()
    name_part = re.sub(r'[,\.\-_]+', ' ', name_part).strip()
    name_part = re.sub(r'\s+', ' ', name_part).strip()

    # Validate name
    if not name_part or len(name_part) < 2 or len(name_part) > 50:
        return None, None
    if not re.match(r'^[A-Za-z][A-Za-z\s\.]{1,49}$', name_part):
        return None, None

    return name_part, phone_clean


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
                    "Ask: which city flying FROM, which city flying TO, and on what date?"
                )
            result = search_google_flights(
                origin=q["origin"], destination=q["destination"],
                date=q["date"], return_date=q.get("return_date"),
                adults=q.get("adults", 1)
            )
            ctx = format_for_shanaya(result, q["origin"], q["destination"], q["date"] or "")
            print(f"[FLIGHTS] {q['origin']}→{q['destination']}: {len(result.get('flights',[]))} results")
            return ctx
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
        name, phone = try_parse_identity(user_message)

        if name and phone:
            info  = create_or_update_lead(session_id, name, phone)
            save_message(session_id, "user", user_message)
            first = name.split()[0]

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
                "reply":       reply,
                "session_id":  session_id,
                "extracted_data": {
                    "contact_name":  name,
                    "contact_phone": phone,   # ← returned so widget stores in localStorage
                },
                "missing_fields": [],
                "is_complete":    False,
                "identity_given": True,
            }
        else:
            save_message(session_id, "user", user_message)
            reply = (
                "Hi there! 👋 Please share your name and phone number so our team can assist you.\n\n"
                "Just type them together — for example:\n"
                "**Rahul Sharma 9876543210**\n\n"
                "No commas or special format needed!"
            )
            save_message(session_id, "assistant", reply)
            return {
                "reply":          reply,
                "session_id":     session_id,
                "extracted_data": {},
                "missing_fields": ["contact_name", "contact_phone"],
                "is_complete":    False,
                "identity_given": False,
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
        "reply":       reply,
        "session_id":  session_id,
        "extracted_data": {
            "contact_name":  existing_lead["contact_name"],
            "contact_phone": existing_lead["contact_phone"],
        },
        "missing_fields": [],
        "is_complete":    False,
        "identity_given": True,
    }


def lookup_packages(*a): return []
