"""SQLAlchemy 2 database engine and session configuration."""
import os
import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from api.config import settings

logger = logging.getLogger(__name__)

def configure_sqlite_engine(target_engine):
    """Attach SQLite connect listener to enforce WAL journal mode, 15s busy timeout, and foreign keys."""
    @event.listens_for(target_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=15000")
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

# SQLite connection args for multi-threaded FastAPI handlers
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False, "timeout": 15.0}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

if settings.DATABASE_URL.startswith("sqlite"):
    configure_sqlite_engine(engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db(target_engine=None):
    """Create all tables defined in Base metadata and run additive migrations."""
    from api import models  # noqa: F401
    from sqlalchemy import text
    eng = target_engine or engine
    try:
        Base.metadata.create_all(bind=eng)
        # Safe additive migration: ensure allocation_id and block_version columns exist on audit_events in SQLite
        if eng.dialect.name == "sqlite":
            with eng.connect() as conn:
                cols = [row[1] for row in conn.execute(text("PRAGMA table_info(audit_events)")).fetchall()]
                if cols and "allocation_id" not in cols:
                    logger.info("Applying additive schema migration: ADD COLUMN allocation_id to audit_events")
                    conn.execute(text("ALTER TABLE audit_events ADD COLUMN allocation_id VARCHAR(36) REFERENCES allocations(id)"))
                    conn.commit()
                if cols and "block_version" not in cols:
                    logger.info("Applying additive schema migration: ADD COLUMN block_version to audit_events (default=1)")
                    conn.execute(text("ALTER TABLE audit_events ADD COLUMN block_version INTEGER NOT NULL DEFAULT 1"))
                    conn.commit()
    except Exception as e:
        logger.error(f"Database schema initialization/migration failed on engine {eng.url}: {e}", exc_info=True)
        raise RuntimeError(f"Database schema migration failed: {e}") from e
