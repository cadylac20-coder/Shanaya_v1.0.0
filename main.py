import os, uuid
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
from database import init_db, get_db
from ai_engine import chat
from actions import actions
from memory import clear_history, get_session_summary
from auth import verify_api_key
from config import ALLOWED_ORIGINS

init_db()
app = FastAPI(title="MKOV Shanaya", version="3.0.0", docs_url="/docs")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["*"], allow_headers=["*"])

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class ActionType(str, Enum):
    GET_CONFIRMATION="get_confirmation"; HOLD_BOOKING="hold_booking"
    CANCEL_BOOKING="cancel_booking"; ADD_ANCILLARY="add_ancillary"
    PAYMENT_LINK="payment_link"; CUSTOM_REQUEST="custom_request"

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None

class ActionRequest(BaseModel):
    action: ActionType; session_id: str
    booking_id: Optional[str] = None; details: Optional[dict] = None

class ChatResponse(BaseModel):
    reply: str; session_id: str
    suggested_actions: list = []; lead_progress: dict = {}; identity_given: bool = False

class ActionResponse(BaseModel):
    status: str; action: str; message: str; data: Optional[dict] = None

@app.get("/")
def root(): return {"status":"online","service":"MKOV Shanaya v3.0"}

@app.get("/health")
def health(): return {"status":"ok"}

@app.get("/widget")
def serve_widget():
    path = os.path.join(STATIC_DIR, "widget.html")
    if os.path.exists(path): return FileResponse(path, media_type="text/html")
    return {"error":"widget.html not found in static/"}

@app.post("/widget/chat", response_model=ChatResponse)
def widget_chat(req: ChatRequest):
    session = req.session_id or str(uuid.uuid4())
    result  = chat(session, req.message)
    return ChatResponse(reply=result["reply"], session_id=session,
        suggested_actions=_suggest(result.get("extracted_data",{})),
        lead_progress=_progress(result.get("extracted_data",{})),
        identity_given=result.get("identity_given", False))

@app.post("/widget/action", response_model=ActionResponse)
def widget_action(req: ActionRequest): return _run(req)

@app.post("/chat", response_model=ChatResponse)
def chat_ep(req: ChatRequest, caller=Depends(verify_api_key)):
    session = req.session_id or str(uuid.uuid4())
    result  = chat(session, req.message)
    return ChatResponse(reply=result["reply"], session_id=session,
        suggested_actions=_suggest(result.get("extracted_data",{})),
        lead_progress=_progress(result.get("extracted_data",{})),
        identity_given=result.get("identity_given", False))

@app.post("/action", response_model=ActionResponse)
def action_ep(req: ActionRequest, caller=Depends(verify_api_key)): return _run(req)

@app.get("/leads")
def get_leads(caller=Depends(verify_api_key)):
    conn = get_db()
    rows = conn.execute(
        "SELECT contact_name,contact_phone,destination,travel_dates,group_size,visit_count,first_seen,last_seen FROM leads WHERE identity_given=1 ORDER BY last_seen DESC"
    ).fetchall()
    conn.close()
    return {"total":len(rows),"leads":[dict(r) for r in rows]}

@app.delete("/chat/{session_id}")
def reset(session_id: str, caller=Depends(verify_api_key)):
    clear_history(session_id); return {"message":"Cleared","session_id":session_id}

@app.get("/chat/{session_id}/summary")
def summary(session_id: str, caller=Depends(verify_api_key)):
    return get_session_summary(session_id)

def _run(req):
    try:
        d = req.details or {}
        if req.action == ActionType.GET_CONFIRMATION: result = actions.get_booking_confirmation(req.session_id, req.booking_id)
        elif req.action == ActionType.HOLD_BOOKING: result = actions.hold_booking(req.session_id, d.get("destination"), d.get("travel_dates"), d.get("duration_hours",24))
        elif req.action == ActionType.CANCEL_BOOKING: result = actions.cancel_booking(req.session_id, req.booking_id or d.get("booking_id"), d.get("reason"))
        elif req.action == ActionType.ADD_ANCILLARY: result = actions.add_ancillary(req.session_id, req.booking_id or d.get("booking_id"), d.get("type"), d.get("details"))
        elif req.action == ActionType.PAYMENT_LINK: result = actions.generate_payment_link(req.session_id, req.booking_id or d.get("booking_id"))
        elif req.action == ActionType.CUSTOM_REQUEST: result = actions.process_custom_request(req.session_id, d.get("request_text","No details"))
        else: result = {"status":"error","message":f"Unknown: {req.action}"}
    except Exception as e: result = {"status":"error","message":str(e)}
    return ActionResponse(status=result.get("status","error"), action=req.action,
        message=result.get("message",""), data={k:v for k,v in result.items() if k not in ("message","status")})

def _suggest(data): return [{"action":"custom_request","label":"📞 Call +91 8010700700","description":"Speak to our team"}]
def _progress(data):
    req=["destination","travel_dates","group_size"]; filled=[f for f in req if data.get(f)]
    return {"filled":filled,"missing":[f for f in req if not data.get(f)],"percent":int(len(filled)/len(req)*100),"complete":len(filled)==len(req)}
