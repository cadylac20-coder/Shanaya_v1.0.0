"""
AI Engine — Shanaya, MKOV Travel Assistant
- Gemini gemini-3.1-flash-lite
- Identity gate: requires Name, Phone_Number before any travel chat
- Visit counter: tells returning users how many times they've chatted
- Per-phone lead tracking across sessions
"""

import re
import google.generativeai as genai
from memory import get_history, save_message
from database import get_db
from config import GEMINI_API_KEY, MODEL, TEMPERATURE, MAX_TOKENS, SYSTEM_PROMPT

print(f"✓ Shanaya AI Engine — {MODEL}")
genai.configure(api_key=GEMINI_API_KEY)


# ── Identity helpers ──────────────────────────────────────────────────────────

def get_lead_by_session(session_id: str):
    """Return lead row for this session, or None."""
    conn = get_db()
    row = conn.execute(
        """SELECT l.* FROM leads l
           JOIN sessions s ON s.lead_id = l.id
           WHERE s.session_id = ?""",
        (session_id,)
    ).fetchone()
    conn.close()
    return row


def get_lead_by_phone(phone: str):
    """Return existing lead for this phone number, or None."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM leads WHERE contact_phone = ?", (phone,)
    ).fetchone()
    conn.close()
    return row


def link_session_to_lead(session_id: str, lead_id: int):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO sessions (session_id, lead_id) VALUES (?, ?)",
        (session_id, lead_id)
    )
    conn.commit()
    conn.close()


def create_or_update_lead(session_id: str, name: str, phone: str) -> dict:
    """
    Create new lead or increment visit_count for returning user.
    Returns dict with name, phone, visit_count, is_returning.
    """
    conn = get_db()
    existing = conn.execute(
        "SELECT * FROM leads WHERE contact_phone = ?", (phone,)
    ).fetchone()

    if existing:
        # Returning user — increment visit count
        new_count = existing["visit_count"] + 1
        conn.execute(
            """UPDATE leads SET visit_count = ?, last_seen = CURRENT_TIMESTAMP,
               contact_name = ? WHERE contact_phone = ?""",
            (new_count, name, phone)
        )
        lead_id = existing["id"]
        conn.commit()
        conn.close()
        link_session_to_lead(session_id, lead_id)
        return {
            "name": name, "phone": phone,
            "visit_count": new_count, "is_returning": True
        }
    else:
        # New user
        cur = conn.execute(
            """INSERT INTO leads (contact_name, contact_phone, identity_given, visit_count)
               VALUES (?, ?, 1, 1)""",
            (name, phone)
        )
        lead_id = cur.lastrowid
        conn.commit()
        conn.close()
        link_session_to_lead(session_id, lead_id)
        return {
            "name": name, "phone": phone,
            "visit_count": 1, "is_returning": False
        }


def try_parse_identity(text: str):
    """Parse 'Name, Phone_Number' from message. Returns (name, phone) or (None, None)."""
    pattern = r'^([A-Za-z][A-Za-z\s\.]{1,48}),\s*(\+?[\d\s\-]{8,15})$'
    m = re.match(pattern, text.strip())
    if m:
        name  = m.group(1).strip()
        phone = re.sub(r'[\s\-]', '', m.group(2).strip())
        if len(phone) >= 8:
            return name, phone
    return None, None


# ── Main chat function ────────────────────────────────────────────────────────

def chat(session_id: str, user_message: str) -> dict:
    print(f"[CHAT] {session_id[:12]} | {user_message[:60]}")

    # ── Check if session already has identity linked ──────────────────────────
    existing_lead = get_lead_by_session(session_id)

    if not existing_lead:
        # No identity for this session yet — try to parse it
        name, phone = try_parse_identity(user_message)

        if name and phone:
            # Identity just provided
            lead_info = create_or_update_lead(session_id, name, phone)
            save_message(session_id, "user", user_message)
            first_name = name.split()[0]

            if lead_info["is_returning"]:
                count = lead_info["visit_count"]
                reply = (
                    f"Welcome back, {first_name}! 🙏 Wonderful to hear from you again.\n\n"
                    f"You've chatted with me **{count} time{'s' if count != 1 else ''}** — "
                    f"I hope I've been helpful each time!\n\n"
                    f"What trip are we planning today?"
                )
            else:
                reply = (
                    f"Wonderful to meet you, {first_name}! 🙏 "
                    f"Welcome to Uniglobe MKOV Travel. I'm Shanaya, your personal travel assistant.\n\n"
                    f"What kind of trip are you dreaming of? Whether it's a beach holiday, "
                    f"honeymoon, adventure, or family trip — I'm here to help!"
                )

            save_message(session_id, "assistant", reply)
            return {
                "reply":          reply,
                "session_id":     session_id,
                "extracted_data": {"contact_name": name, "contact_phone": phone},
                "missing_fields": [],
                "is_complete":    False,
                "identity_given": True,
            }
        else:
            # Still no identity — keep asking
            save_message(session_id, "user", user_message)
            reply = (
                "Hi there! 👋 Before we get started, I need your name and phone number "
                "so our team can assist you better.\n\n"
                "Please reply in this format:\n**Name, Phone_Number**\n\n"
                "Example: Rahul Sharma, 9876543210"
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

    # ── Identity confirmed — normal Gemini chat ───────────────────────────────
    save_message(session_id, "user", user_message)
    history = get_history(session_id)

    contents = []
    for msg in history[:-1]:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    try:
        gemini_model = genai.GenerativeModel(
            model_name=MODEL,
            system_instruction=SYSTEM_PROMPT,
        )
        chat_session = gemini_model.start_chat(history=contents)
        response = chat_session.send_message(
            user_message,
            generation_config={
                "temperature": TEMPERATURE,
                "max_output_tokens": MAX_TOKENS,
            },
        )
        reply = response.text.strip() if response.text else "Could you repeat that? 🙏"
        print(f"[CHAT] ✓ {reply[:80]}")

    except Exception as e:
        import traceback; traceback.print_exc()
        reply = (
            "I'm having a brief technical issue. 🙏 "
            "Please try again, or call our team at **+91 8010700700**."
        )

    save_message(session_id, "assistant", reply)
    return {
        "reply":          reply,
        "session_id":     session_id,
        "extracted_data": {"contact_name": existing_lead["contact_name"]},
        "missing_fields": [],
        "is_complete":    False,
        "identity_given": True,
    }


def lookup_packages(destination, budget, dates, group):
    return []
