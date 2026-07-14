import os
import sqlite3
import libsql

TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN    = os.getenv("TURSO_AUTH_TOKEN")

if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
    raise RuntimeError(
        "TURSO_DATABASE_URL and TURSO_AUTH_TOKEN must be set in environment variables."
    )


def get_db():
    conn = libsql.connect(database=TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            key        TEXT UNIQUE NOT NULL,
            name       TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            active     INTEGER DEFAULT 1
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_name   TEXT,
            contact_phone  TEXT UNIQUE,
            destination    TEXT,
            travel_dates   TEXT,
            group_size     INTEGER,
            trip_type      TEXT,
            identity_given INTEGER DEFAULT 0,
            visit_count    INTEGER DEFAULT 1,
            first_seen     DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen      DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            lead_id    INTEGER REFERENCES leads(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # NEW — holds a partial identity (name given but no phone yet, or vice versa)
    # so Shanaya only asks for the ONE missing piece instead of repeating
    # the whole request.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_identity (
            session_id TEXT UNIQUE NOT NULL,
            name       TEXT,
            phone      TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id     TEXT UNIQUE NOT NULL,
            session_id     TEXT NOT NULL,
            reference_code TEXT NOT NULL,
            destination    TEXT,
            travel_dates   TEXT,
            group_size     INTEGER,
            total_price    INTEGER,
            email          TEXT,
            status         TEXT DEFAULT 'confirmed',
            created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
            cancelled_at   DATETIME
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS holds (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   TEXT NOT NULL,
            hold_id      TEXT UNIQUE NOT NULL,
            destination  TEXT,
            travel_dates TEXT,
            hours        INTEGER DEFAULT 24,
            status       TEXT DEFAULT 'active',
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ancillaries (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id   TEXT NOT NULL,
            ancillary_id TEXT UNIQUE NOT NULL,
            type         TEXT NOT NULL,
            price        INTEGER NOT NULL,
            details      TEXT,
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id    TEXT UNIQUE NOT NULL,
            session_id   TEXT NOT NULL,
            request_text TEXT NOT NULL,
            status       TEXT DEFAULT 'open',
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    from config import DEFAULT_API_KEY
    conn.execute(
        "INSERT OR IGNORE INTO api_keys (key, name) VALUES (?, ?)",
        (DEFAULT_API_KEY, "Development Key")
    )
    conn.commit()
    print("✓ Shanaya DB ready on Turso")
