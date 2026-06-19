from database import get_db
def get_lead_data(session_id):
    conn=get_db(); row=conn.execute("SELECT l.* FROM leads l JOIN sessions s ON s.lead_id=l.id WHERE s.session_id=?",(session_id,)).fetchone(); conn.close()
    return dict(row) if row else {}
