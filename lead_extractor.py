import json
import google.generativeai as genai
from database import get_db
from config import GEMINI_API_KEY, MODEL

genai.configure(api_key=GEMINI_API_KEY)

# Purged budget tracking from required fields entirely
REQUIRED_FIELDS = ["destination", "travel_dates", "group_size"]

def extract_and_track(session_id: str, user_message: str) -> dict:
    prompt = f'Extract the following travel details from the message: destination, travel_dates, group_size, trip_type, contact_name, contact_phone. Message: "{user_message}". Return ONLY a clean JSON object.'
    try:
        model = genai.GenerativeModel(MODEL)
        response = model.generate_content(prompt)
        raw = response.text.strip().replace("```json", "").replace("```", "").strip()
        extracted = json.loads(raw)
    except:
        extracted = {"destination": None, "travel_dates": None, "group_size": None, "trip_type": None, "contact_name": None, "contact_phone": None}
    
    conn = get_db()
    existing = conn.execute("SELECT * FROM leads WHERE session_id = ?", (session_id,)).fetchone()
    
    current_data = {
        "destination": extracted.get("destination") or (existing["destination"] if existing else None),
        "travel_dates": extracted.get("travel_dates") or (existing["travel_dates"] if existing else None),
        "group_size": extracted.get("group_size") or (existing["group_size"] if existing else None),
        "trip_type": extracted.get("trip_type") or (existing["trip_type"] if existing else None),
        "contact_name": extracted.get("contact_name") or (existing["contact_name"] if existing else None),
        "contact_phone": extracted.get("contact_phone") or (existing["contact_phone"] if existing else None),
    }
    
    missing = [f for f in REQUIRED_FIELDS if not current_data.get(f)]
    is_complete = len(missing) == 0

    if existing:
        conn.execute(
            "UPDATE leads SET destination=?, travel_dates=?, group_size=?, trip_type=?, contact_name=?, contact_phone=?, is_complete=? WHERE session_id=?",
            (current_data["destination"], current_data["travel_dates"], current_data["group_size"], current_data["trip_type"], current_data["contact_name"], current_data["contact_phone"], int(is_complete), session_id)
        )
    else:
        conn.execute(
            "INSERT INTO leads (session_id, destination, travel_dates, group_size, trip_type, contact_name, contact_phone, is_complete) VALUES (?,?,?,?,?,?,?,?)",
            (session_id, current_data["destination"], current_data["travel_dates"], current_data["group_size"], current_data["trip_type"], current_data["contact_name"], current_data["contact_phone"], int(is_complete))
        )
    conn.commit()
    conn.close()
    
    return {"extracted": extracted, "current_data": current_data, "missing_fields": missing, "complete": is_complete}
