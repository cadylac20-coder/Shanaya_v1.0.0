from database import get_db


def get_lead_data(session_id: str) -> dict:
    conn = get_db()
    row  = conn.execute(
        """SELECT l.* FROM leads l
           JOIN sessions s ON s.lead_id = l.id
           WHERE s.session_id = ?""",
        (session_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


def update_lead_field(session_id: str, **kwargs):
    conn  = get_db()
    lead  = conn.execute(
        """SELECT l.id FROM leads l
           JOIN sessions s ON s.lead_id = l.id
           WHERE s.session_id = ?""",
        (session_id,)
    ).fetchone()
    if lead:
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [lead["id"]]
        conn.execute(
            f"UPDATE leads SET {sets}, last_seen=CURRENT_TIMESTAMP WHERE id=?", vals
        )
        conn.commit()
    conn.close()
