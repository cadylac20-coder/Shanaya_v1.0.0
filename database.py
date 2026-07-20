"""
database.py — Shanaya Chatbot Database (Turso / libSQL)

IMPORTANT: libsql's Connection object is a Rust extension type and
does NOT support `conn.row_factory = sqlite3.Row` like a normal
sqlite3.Connection does (it has no __dict__ to set attributes on).

To keep `row["column_name"]` access working everywhere else in the
codebase unchanged, this file wraps the raw libsql connection/cursor
in thin Python classes that provide dict-style row access manually,
using the cursor's `.description` to map column names to values.
"""

import os
import libsql

TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN    = os.getenv("TURSO_AUTH_TOKEN")

if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
    raise RuntimeError(
        "TURSO_DATABASE_URL and TURSO_AUTH_TOKEN must be set. "
        "Sign up free at https://turso.tech and add them to your "
        "Render environment variables."
    )


class Row:
    """
    Dict-like wrapper around a raw row tuple + column names.
    Mimics sqlite3.Row so existing code using row["column"] keeps
    working unchanged.
    """
    __slots__ = ("_cols", "_data")

    def __init__(self, cols, data):
        self._cols = cols
        self._data = data

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._data[self._cols.index(key)]
        return self._data[key]

    def keys(self):
        return list(self._cols)

    def __iter__(self):
        return iter(self._data)

    def __repr__(self):
        return f"Row({dict(zip(self._cols, self._data))})"


class CursorWrapper:
    """Wraps a raw libsql cursor to return Row objects instead of tuples."""

    def __init__(self, cursor):
        self._cursor = cursor

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in (self._cursor.description or [])]
        return Row(cols, row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        cols = [d[0] for d in (self._cursor.description or [])]
        return [Row(cols, r) for r in rows]

    @property
    def lastrowid(self):
        return getattr(self._cursor, "lastrowid", None)


class ConnectionWrapper:
    """
    Wraps a raw libsql connection so conn.execute(...) returns a
    CursorWrapper (dict-row access), while commit()/close() pass
    through untouched. This keeps every other file in the codebase
    (ai_engine.py, memory.py, auth.py, actions.py, main.py) working
    exactly as before — they only ever call conn.execute(...).fetchone()
    and index into the result with ["column_name"].
    """

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        if params is None:
            cur = self._conn.execute(sql)
        else:
            cur = self._conn.execute(sql, params)
        return CursorWrapper(cur)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def get_db():
    raw_conn = libsql.connect(database=TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
    return ConnectionWrapper(raw_conn)


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
    print("✓ Shanaya DB ready on Turso — permanent, survives all restarts")
