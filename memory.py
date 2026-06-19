from database import get_db
from config import MAX_HISTORY

def get_history(session_id):
    conn=get_db(); rows=conn.execute("SELECT role,content FROM conversations WHERE session_id=? ORDER BY id DESC LIMIT ?",(session_id,MAX_HISTORY)).fetchall(); conn.close()
    return [{"role":r["role"],"content":r["content"]} for r in reversed(rows)]

def save_message(session_id,role,content):
    conn=get_db(); conn.execute("INSERT INTO conversations (session_id,role,content) VALUES (?,?,?)",(session_id,role,content)); conn.commit(); conn.close()

def clear_history(session_id):
    conn=get_db(); conn.execute("DELETE FROM conversations WHERE session_id=?",(session_id,)); conn.commit(); conn.close()

def get_session_summary(session_id):
    conn=get_db()
    msgs=conn.execute("SELECT role,content FROM conversations WHERE session_id=? ORDER BY id",(session_id,)).fetchall()
    lead=conn.execute("SELECT l.contact_name,l.contact_phone,l.visit_count FROM leads l JOIN sessions s ON s.lead_id=l.id WHERE s.session_id=?",(session_id,)).fetchone()
    conn.close()
    return {"session_id":session_id,"message_count":len(msgs),"first_message":msgs[0]["content"] if msgs else None,"last_message":msgs[-1]["content"] if msgs else None,"lead":dict(lead) if lead else {}}
