import os
import libsql

TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN    = os.getenv("TURSO_AUTH_TOKEN")

if not TURSO_DATABASE_URL:
    raise RuntimeError("TURSO_DATABASE_URL not set. Add it in Render → Environment.")
if not TURSO_AUTH_TOKEN:
    raise RuntimeError("TURSO_AUTH_TOKEN not set. Add it in Render → Environment.")


class _Row(list):
    """
    Minimal drop-in replacement for sqlite3.Row so existing code
    (row["contact_phone"], row["visit_count"], etc.) keeps working —
    no sqlite3 import, no local database, Turso only.
    """
    def __init__(self, columns, row):
        self._columns = columns
        super().__init__(row)

    def __getitem__(self, key):
        if isinstance(key, str):
            return list.__getitem__(self, self._columns.index(key))
        return list.__getitem__(self, key)

    def keys(self):
        return list(self._columns)


class _CursorWrapper:
    """
    Wraps the native libsql Cursor. The native object is a compiled
    extension type — it has no row_factory hook, so instead of trying
    to attach one, we intercept fetchone()/fetchall() here and convert
    each raw row into a _Row using cursor.description for column names.
    """
    def __init__(self, cursor):
        self._cursor = cursor

    def _columns(self):
        return [d[0] for d in (self._cursor.description or [])]

    def execute(self, sql, params=None):
        if params is None:
            self._cursor.execute(sql)
        else:
            self._cursor.execute(sql, params)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return _Row(self._columns(), row)

    def fetchall(self):
        cols = self._columns()
        return [_Row(cols, row) for row in self._cursor.fetchall()]

    def __getattr__(self, name):
        # passthrough for anything else (rowcount, lastrowid, close, etc.)
        return getattr(self._cursor, name)


class _ConnectionWrapper:
    """Wraps the native libsql Connection so conn.execute(...) and conn.cursor() both return row-aware cursors."""
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return _CursorWrapper(self._conn.cursor())

    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_db():
    """Connection to Turso (libSQL). This is the ONLY database backend — no local SQLite fallback."""
    raw_conn = libsql.connect(TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
    return _ConnectionWrapper(raw_conn)


print("✅ Shanaya DB — connected to Turso (libSQL): data is permanent")


def init_db():
    conn = get_db()
    c    = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            key        TEXT UNIQUE NOT NULL,
            name       TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            active     INTEGER DEFAULT 1
        )
    """)

    # One row per unique phone number
    c.execute("""
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

    # Maps session_id → lead_id
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            lead_id    INTEGER REFERENCES leads(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Holds a name OR phone given before the other half arrives,
    # so Shanaya can ask for only the missing piece instead of restarting.
    c.execute("""
        CREATE TABLE IF NOT EXISTS partial_identity (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id    TEXT UNIQUE NOT NULL,
            partial_name  TEXT,
            partial_phone TEXT,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
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

    c.execute("""
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

    c.execute("""
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

    c.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id    TEXT UNIQUE NOT NULL,
            session_id   TEXT NOT NULL,
            request_text TEXT NOT NULL,
            status       TEXT DEFAULT 'open',
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    from config import DEFAULT_API_KEY
    c.execute(
        "INSERT OR IGNORE INTO api_keys (key, name) VALUES (?, ?)",
        (DEFAULT_API_KEY, "Development Key")
    )

    conn.commit()
    conn.close()
    print("✓ Shanaya DB ready — Turso (libSQL)")
