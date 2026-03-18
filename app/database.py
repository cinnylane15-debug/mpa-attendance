from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def enable_pgvector():
    """Enable pgvector extension in the database."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()


def create_tables():
    """Create all tables in the database."""
    enable_pgvector()
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def _run_migrations():
    """Add new columns to existing tables if they don't exist."""
    migrations = [
        ("cameras", "capture_mode", "ALTER TABLE cameras ADD COLUMN capture_mode VARCHAR(8) NOT NULL DEFAULT 'snapshot'"),
        ("cameras", "snapshot_url", "ALTER TABLE cameras ADD COLUMN snapshot_url VARCHAR(500)"),
    ]
    with engine.connect() as conn:
        for table, column, sql in migrations:
            result = conn.execute(text(
                "SELECT 1 FROM information_schema.columns WHERE table_name=:t AND column_name=:c"
            ), {"t": table, "c": column})
            if result.fetchone() is None:
                conn.execute(text(sql))
        conn.commit()


def get_db():
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
