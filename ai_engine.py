import google.generativeai as genai
from memory import get_history, save_message
from config import GEMINI_API_KEY, MODEL, TEMPERATURE, MAX_TOKENS, SYSTEM_PROMPT

print(f"✓ AI Engine loaded — Model: {MODEL}")
genai.configure(api_key=GEMINI_API_KEY)

def chat(session_id: str, user_message: str) -> dict:
    print(f"[CHAT] Session: {session_id}, Message: {user_message[:50]}")

    # Save user message first
    save_message(session_id, "user", user_message)

    # Build conversation history for context
    history = get_history(session_id)

    # Convert history into Gemini-compatible contents list
    contents = []
    for msg in history[:-1]:  # exclude the message we just saved (sent separately)
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    try:
        print(f"[CHAT] Creating Gemini model: {MODEL}")
        model = genai.GenerativeModel(
            model_name=MODEL,
            system_instruction=SYSTEM_PROMPT,
        )

        # Start chat with history, then send latest message
        chat_session = model.start_chat(history=contents)
        response = chat_session.send_message(
            user_message,
            generation_config={
                "temperature": TEMPERATURE,
                "max_output_tokens": MAX_TOKENS,
            },
        )

        reply = response.text.strip() if response.text else "I didn't get a response. Could you repeat that?"
        print(f"[CHAT] ✓ Got reply: {reply[:80]}")

    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        reply = (
            "I'm having a brief technical issue. "
            "Please try again in a moment, or call us directly at +91-120-XXXXXX. 🙏"
        )

    # Save assistant reply
    save_message(session_id, "assistant", reply)

    # Return minimal data (DON'T call lead_extractor to avoid rate limit)
    return {
        "reply":          reply,
        "session_id":     session_id,
        "extracted_data": {},
        "missing_fields":  [],
        "is_complete":    False,
    }


def lookup_packages(destination, budget, dates, group):
    """Stub — packages are handled via SYSTEM_PROMPT knowledge."""
    return []
