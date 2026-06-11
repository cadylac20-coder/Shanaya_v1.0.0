"""
AI Engine for Shaina — MKOV Travel Assistant
Uses Gemini gemini-3.1-flash-lite with full conversation history.
Handles identity gate: requires Name, Phone_Number before any travel chat.
"""

import re
import google.generativeai as genai
from memory import get_history, save_message
from database import get_db
from config import GEMINI_API_KEY, MODEL, TEMPERATURE, MAX_TOKENS, SYSTEM_PROMPT

print(f"✓ Shaina AI Engine loaded — {MODEL}")
genai.configure(api_key=GEMINI_API_KEY)


# ── Identity helpers ──────────────────────────────────────────────────────────

def get_identity_status(session_id: str) -> dict:
    """Return whether this session has already given name + phone."""
    conn = get_db()
    row = conn.execute(
        "SELECT contact_name, contact_phone, identity_given FROM leads WHERE session_id=?",
        (session_id,)
    ).fetchone()
    conn.close()
    if row and row["identity_given"]:
        return {"given": True, "name": row["contact_name"], "phone": row["contact_phone"]}
    return {"given": False, "name": None, "phone": None}


def try_parse_identity(text: str):
    """
    Try to parse 'Name, Phone_Number' from user message.
    Returns (name, phone) or (None, None).
    """
    # Pattern: any text, comma, 10-digit number (with optional spaces/dashes)
    pattern = r'^([A-Za-z\s\.]{2,50}),\s*(\+?[\d\s\-]{8,15})$'
    m = re.match(pattern, text.strip())
    if m:
        name  = m.group(1).strip()
        phone = re.sub(r'[\s\-]', '', m.group(2).strip())
        return name, phone
    return None, None


def save_identity(session_id: str, name: str, phone: str):
    """Persist name + phone to leads table."""
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM leads WHERE session_id=?", (session_id,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE leads SET contact_name=?, contact_phone=?, identity_given=1, updated_at=CURRENT_TIMESTAMP WHERE session_id=?",
            (name, phone, session_id)
        )
    else:
        conn.execute(
            "INSERT INTO leads (session_id, contact_name, contact_phone, identity_given) VALUES (?,?,?,1)",
            (session_id, name, phone)
        )
    conn.commit()
    conn.close()
    print(f"[IDENTITY] Saved: {name} / {phone} for session {session_id}")


# ── Main chat function ────────────────────────────────────────────────────────

def chat(session_id: str, user_message: str) -> dict:
    print(f"[CHAT] Session: {session_id[:12]} | Msg: {user_message[:60]}")

    # ── Step 1: Check identity gate ───────────────────────────────────────────
    identity = get_identity_status(session_id)

    if not identity["given"]:
        # Try to parse identity from this message
        name, phone = try_parse_identity(user_message)
        if name and phone:
            # Identity just provided — save it and greet
            save_identity(session_id, name, phone)
            save_message(session_id, "user", user_message)
            first_name = name.split()[0]
            reply = (
                f"Wonderful to meet you, {first_name}! 🙏 "
                f"Welcome to Uniglobe MKOV Travel. I'm Shaina, your personal travel assistant.\n\n"
                f"What kind of trip are you dreaming of? Whether it's a beach holiday, "
                f"honeymoon, family trip, or adventure — I'm here to help!"
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
            # Identity not given yet — keep asking regardless of what they typed
            save_message(session_id, "user", user_message)
            reply = (
                "Hi there! 👋 Before we get started, I need your name and phone number "
                "so our team can assist you better.\n\n"
                "Please reply in this format:\n"
                "**Name, Phone_Number**\n\n"
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

    # ── Step 2: Identity given — proceed with normal AI chat ─────────────────
    save_message(session_id, "user", user_message)
    history = get_history(session_id)

    # Build Gemini-compatible history (exclude last message, sent separately)
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
        reply = response.text.strip() if response.text else "I didn't catch that — could you repeat? 🙏"
        print(f"[CHAT] ✓ Reply: {reply[:80]}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ERROR] {type(e).__name__}: {e}")
        reply = (
            "I'm having a brief technical issue. 🙏 "
            "Please try again in a moment, or call our team directly."
        )

    save_message(session_id, "assistant", reply)

    return {
        "reply":          reply,
        "session_id":     session_id,
        "extracted_data": {"contact_name": identity["name"]},
        "missing_fields": [],
        "is_complete":    False,
        "identity_given": True,
    }


def lookup_packages(destination, budget, dates, group):
    return []
