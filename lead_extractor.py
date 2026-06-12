"""
Lead extractor — kept minimal.
Identity gate (name + phone) is handled directly in ai_engine.py.
This module is only used if you want to extract additional
structured data from messages in the future.
"""

from database import get_db

REQUIRED_FIELDS = ["destination", "travel_dates", "group_size"]


def get_lead_data(session_id: str) -> dict:
    """Return current lead data for a session."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM leads WHERE session_id = ?", (session_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


def update_lead(session_id: str, **kwargs):
    """Update specific fields on a lead record."""
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM leads WHERE session_id=?", (session_id,)
    ).fetchone()
    if existing:
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [session_id]
        conn.execute(
            f"UPDATE leads SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE session_id=?", vals
        )
    else:
        cols = "session_id, " + ", ".join(kwargs.keys())
        placeholders = "?, " + ", ".join("?" for _ in kwargs)
        conn.execute(
            f"INSERT INTO leads ({cols}) VALUES ({placeholders})",
            [session_id] + list(kwargs.values())
        )
    conn.commit()
    conn.close()
