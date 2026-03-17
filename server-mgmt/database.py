import aiosqlite
from config import settings

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(settings.db_path)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None


async def init_db():
    """Create tables if they don't exist."""
    db = await get_db()

    await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            key_hash TEXT NOT NULL,
            key_prefix TEXT NOT NULL,
            created_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER,
            action TEXT NOT NULL,
            detail TEXT,
            ip_address TEXT,
            success BOOLEAN DEFAULT 1
        );

        CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
        CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(key_prefix);
    """)

    # Create default admin user if not exists
    from auth import hash_password
    row = await db.execute_fetchall(
        "SELECT id FROM users WHERE username = ?", (settings.admin_username,)
    )
    if not row:
        password_hash = hash_password(settings.admin_password)
        await db.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (settings.admin_username, password_hash, "admin"),
        )
        await db.commit()


async def log_audit(
    action: str,
    user_id: int | None = None,
    detail: str | None = None,
    ip_address: str | None = None,
    success: bool = True,
):
    db = await get_db()
    await db.execute(
        "INSERT INTO audit_log (user_id, action, detail, ip_address, success) VALUES (?, ?, ?, ?, ?)",
        (user_id, action, detail, ip_address, success),
    )
    await db.commit()
