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
class DictRow:
    """Mimics sqlite3.Row: supports row["col"], row[0], dict(row), len(row)."""
    __slots__ = ("_values", "_columns")

    def __init__(self, values, columns):
        self._values  = values
        self._columns = columns

    def __getitem__(self, key):
        if isinstance(key, str):
            try:
                idx = self._columns.index(key)
            except ValueError:
                raise KeyError(key)
            return self._values[idx]
        return self._values[key]

    def keys(self):
        return list(self._columns)

    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, IndexError):
            return default

    def __contains__(self, key):
        return key in self._columns

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __repr__(self):
        return f"DictRow({dict(zip(self._columns, self._values))!r})"


class _CursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=None):
        if params is None:
            self._cursor.execute(sql)
        else:
            self._cursor.execute(sql, params)
        return self

    def _columns(self):
        desc = self._cursor.description or []
        return [d[0] for d in desc]

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return DictRow(row, self._columns())

    def fetchall(self):
        rows = self._cursor.fetchall()
        cols = self._columns()
        return [DictRow(r, cols) for r in rows]

    @property
    def lastrowid(self):
        return getattr(self._cursor, "lastrowid", None)


class _ConnWrapper:
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        cur = self._conn.cursor()
        if params is None:
            cur.execute(sql)
        else:
            cur.execute(sql, params)
        return _CursorWrapper(cur)

    def cursor(self):
        return _CursorWrapper(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def close(self):
        close_fn = getattr(self._conn, "close", None)
        if callable(close_fn):
            close_fn()


def get_db():
    """
    Return a Turso connection with sqlite3.Row-style access
    (row["column_name"] works exactly like before).
    """
    raw_conn = libsql.connect(
        database=TURSO_DATABASE_URL,
        auth_token=TURSO_AUTH_TOKEN,
    )
    return _ConnWrapper(raw_conn)


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

    # One row per unique phone number — permanent across every restart
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

    # Maps session_id → lead_id
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            lead_id    INTEGER REFERENCES leads(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
