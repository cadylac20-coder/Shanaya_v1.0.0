"""
MKOV Shaina Travel AI — FastAPI Application
v1.0.0 — Custom Gated Access & Restricted Travel Logic Array
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import uuid
import os
import re

from database import init_db, get_db
from ai_engine import chat
from memory import clear_history, get_session_summary
from auth import verify_api_key
from config import ALLOWED_ORIGINS

init_db()

app = FastAPI(
    title="MKOV Shaina Travel AI",
    description="AI Travel Assistant Shaina featuring strict contact validation gating",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class ChatRequest(BaseModel):
    message: str = Field(..., description="User chat input")
    session_id: str = Field(default=None, description="Unique tracking session identifier")

@app.post("/chat")
def handle_chat(req: ChatRequest, caller=Depends(verify_api_key)):
    session_id = req.session_id or f"MKOV-{str(uuid.uuid4())[:8].upper()}"
    raw_message = req.message.strip()
    
    conn = get_db()
    profile = conn.execute("SELECT * FROM user_profiles WHERE session_id = ?", (session_id,)).fetchone()
    
    # ── Strict Onboarding Gate Verification ──────────────────────────────────
    if not profile:
        # Check if incoming format precisely matches "Name,Phone_Number"
        match = re.match(r"^([^,]+),\s*(\+?\d[\d-\s]{7,14})$", raw_message)
        if not match:
            conn.close()
            return {
                "reply": "Welcome to Uniglobe MKOV Travel! Before we can look up itineraries or assist with travel services, please introduce yourself by typing your Name and Phone Number in this exact format:\n\n**Name,Phone_Number**\n\n*Example: Rahul Sharma,9876543210*",
                "session_id": session_id,
                "is_authorized": False,
                "extracted_data": {},
                "missing_fields": ["name_phone_auth"],
                "is_complete": False
            }
        
        # Valid pattern captured -> Extract and write to backend master list
        extracted_name = match.group(1).strip()
        extracted_phone = match.group(2).strip()
        
        try:
            conn.execute(
                "INSERT INTO user_profiles (session_id, full_name, phone_number) VALUES (?, ?, ?)",
                (session_id, extracted_name, extracted_phone)
            )
            conn.commit()
        except Exception as e:
            pass  # Fallthrough if session race condition happens
        
        conn.close()
        return {
            "reply": f"Thank you, {extracted_name}! Your details have been securely logged in our tour deck system. How can I assist you with your Uniglobe MKOV travel plans today?",
            "session_id": session_id,
            "is_authorized": True,
            "extracted_data": {"contact_name": extracted_name, "contact_phone": extracted_phone},
            "missing_fields": [],
            "is_complete": False
        }
    
    conn.close()
    
    # User is authorized -> Hand off execution directly to AI Chat Engine
    ai_response = chat(session_id, raw_message)
    ai_response["is_authorized"] = True
    return ai_response

@app.get("/admin/users")
def get_authorized_users(caller=Depends(verify_api_key)):
    """Backend Administrative endpoint to view the logged authorized client base."""
    conn = get_db()
    rows = conn.execute("SELECT session_id, full_name, phone_number, authorized_at FROM user_profiles ORDER BY authorized_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/")
def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "Active", "engine": "Shaina Travel AI Engine"}
