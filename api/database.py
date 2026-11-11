"""SQLAlchemy 2 database engine and session configuration."""
import os
import sys
import errno
import ctypes
import logging
import uuid
import sqlite3
from typing import Optional, List
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

def check_sqlite_integrity(db_path: str) -> bool:
    """Run PRAGMA quick_check on a database file to verify it is valid and uncorrupted."""
    if not os.path.exists(db_path) or not os.path.isfile(db_path):
        return False
    if os.path.getsize(db_path) == 0:
        return False
    try:
        conn = sqlite3.connect(f"file:{os.path.abspath(db_path)}?mode=ro", uri=True, timeout=5.0)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA quick_check")
            res = cursor.fetchone()
            cursor.close()
            return res is not None and res[0] == "ok"
        finally:
            conn.close()
    except Exception:
        return False

def cleanup_temp_db_files(base_tmp_path: str):
    """Clean up this process's own temporary database file and any SQLite WAL/SHM companion files."""
    for path in [base_tmp_path, f"{base_tmp_path}-wal", f"{base_tmp_path}-shm"]:
        if os.path.exists(path):
            try:
                os.unlink(path)
            except OSError:
                pass

def atomic_publish_no_overwrite(src: str, dst: str) -> bool:
    """
    Atomically publish temporary database file `src` to final path `dst` without overwriting an existing destination.
    Uses os.link() as the primary atomic primitive.
    If hard-links are unsupported by the filesystem, falls back to platform-native atomic no-replace primitives:
      - Darwin (macOS): renamex_np(..., RENAME_EXCL)
      - Linux: renameat2(..., RENAME_NOREPLACE)
      - Windows: MoveFileExW(..., 0)
    If no genuinely atomic no-replace primitive is available, fails closed with RuntimeError.
    Never uses check-then-act os.rename() or os.replace().
    Returns True if this process published the destination.
    Returns False if another process published the destination first (FileExistsError/EEXIST).
    """
    # 1. Primary publication primitive: os.link()
    try:
        os.link(src, dst)
        return True
    except FileExistsError:
        return False
    except OSError as link_err:
        unsupported_errnos = {
            errno.EPERM,
            errno.ENOSYS,
            getattr(errno, "EOPNOTSUPP", None),
            getattr(errno, "ENOTSUP", None),
            errno.EXDEV,
            errno.EMLINK,
        }
        if link_err.errno not in {e for e in unsupported_errnos if e is not None}:
            raise RuntimeError(f"Unexpected filesystem link error publishing to '{dst}': {link_err}") from link_err

    # 2. Platform-native atomic no-replace fallbacks when hard-links are unsupported
    # 2a. Darwin (macOS): renamex_np with RENAME_EXCL (0x00000004)
    if sys.platform == "darwin":
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            if hasattr(libc, "renamex_np"):
                ret = libc.renamex_np(src.encode("utf-8"), dst.encode("utf-8"), 4)
                if ret == 0:
                    return True
                err = ctypes.get_errno()
                if err == errno.EEXIST:
                    return False
                raise OSError(err, os.strerror(err))
        except Exception as e:
            if isinstance(e, OSError) and e.errno == errno.EEXIST:
                return False
            raise RuntimeError(f"Platform atomic no-replace publication failed on Darwin: {e}") from e

    # 2b. Linux: renameat2 with RENAME_NOREPLACE (1)
    elif sys.platform.startswith("linux"):
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            if hasattr(libc, "renameat2"):
                ret = libc.renameat2(-100, src.encode("utf-8"), -100, dst.encode("utf-8"), 1)
                if ret == 0:
                    return True
                err = ctypes.get_errno()
                if err == errno.EEXIST:
                    return False
                raise OSError(err, os.strerror(err))
        except Exception as e:
            if isinstance(e, OSError) and e.errno == errno.EEXIST:
                return False
            raise RuntimeError(f"Platform atomic no-replace publication failed on Linux: {e}") from e

    # 2c. Windows (NT)
    elif os.name == "nt":
        try:
            kernel32 = ctypes.windll.kernel32
            ret = kernel32.MoveFileExW(ctypes.c_wchar_p(src), ctypes.c_wchar_p(dst), ctypes.c_uint32(0))
            if ret != 0:
                return True
            err = kernel32.GetLastError()
            if err in (80, 183):
                return False
            raise OSError(err, f"MoveFileExW failed with Windows error code {err}")
        except Exception as e:
            raise RuntimeError(f"Platform atomic no-replace publication failed on Windows: {e}") from e

    # 3. If no safe no-replace primitive is available, fail closed.
    raise RuntimeError(
        f"Atomic no-overwrite publication of '{dst}' is not supported on this platform/filesystem. "
        f"Refusing unsafe publication."
    )

def ensure_sqlite_directory(db_url: str, candidate_sources: Optional[List[str]] = None):
    """
    Ensure directory exists for SQLite database URL and atomically migrate from existing root database.
    Uses sqlite3.Connection.backup() to ensure WAL transactions are preserved and publication is atomic.
    """
    if not db_url.startswith("sqlite"):
        return
    raw_path = db_url.replace("sqlite:///", "", 1)
    if not raw_path or raw_path == ":memory:":
        return
    abs_path = os.path.abspath(raw_path)
    parent_dir = os.path.dirname(abs_path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)

    # 1. If destination database already exists, verify its integrity. Never overwrite an existing destination.
    if os.path.exists(abs_path):
        if not check_sqlite_integrity(abs_path):
            logger.error("Destination database '%s' exists but failed integrity verification.", abs_path)
            raise RuntimeError(
                f"Destination database '{abs_path}' exists but failed integrity verification (corrupt or incomplete). "
                f"Manual recovery required; refusing to overwrite or initialize."
            )
        return

    # 2. Locate source candidate database for initial volume seeding
    # NOTE: Startup cleanup of other processes' temporary files is strictly omitted to avoid deleting
    # an active backup currently being written by a concurrent process.
    if candidate_sources is None:
        candidate_sources = [
            os.path.join(os.getcwd(), "disaster_healthcare.db"),
            "/app/disaster_healthcare.db",
        ]

    source_candidate = None
    for cand in candidate_sources:
        if os.path.isfile(cand) and os.path.abspath(cand) != abs_path:
            source_candidate = cand
            break

    if not source_candidate:
        # No source database candidate found; allow standard fresh schema initialization
        return

    # 3. Verify candidate source database integrity before migrating
    if not check_sqlite_integrity(source_candidate):
        logger.error("Source candidate database '%s' is corrupt or incomplete.", source_candidate)
        raise RuntimeError(
            f"Source candidate database '{source_candidate}' failed integrity verification. "
            f"Refusing to migrate corrupt source database."
        )

    # 4. Perform WAL-safe consistent backup using sqlite3.Connection.backup()
    tmp_filename = f".migrating_{uuid.uuid4().hex}_{os.path.basename(abs_path)}.tmp"
    dest_tmp_path = os.path.join(parent_dir, tmp_filename)
    try:
        logger.info("Migrating source database from %s to %s via SQLite Backup API", source_candidate, abs_path)
        src_uri = f"file:{os.path.abspath(source_candidate)}?mode=ro"
        src_conn = sqlite3.connect(src_uri, uri=True, timeout=15.0)
        try:
            dst_conn = sqlite3.connect(dest_tmp_path, timeout=15.0)
            try:
                # Pager-level consistent snapshot including all committed WAL transactions
                src_conn.backup(dst_conn)
                dst_conn.commit()
            finally:
                dst_conn.close()
        finally:
            src_conn.close()

        # 5. Verify integrity of completed temporary backup file
        if not check_sqlite_integrity(dest_tmp_path):
            raise RuntimeError(f"Integrity check failed on migrated temporary database '{dest_tmp_path}'.")

        # 6. Safe atomic publication without overwriting an existing destination
        published = atomic_publish_no_overwrite(dest_tmp_path, abs_path)
        if published:
            logger.info("Successfully published migrated database at %s", abs_path)
        else:
            logger.info("Destination %s was published concurrently by another process.", abs_path)

        # 7. Final verification of published destination
        if not check_sqlite_integrity(abs_path):
            raise RuntimeError(f"Published destination database '{abs_path}' failed integrity verification.")

    except Exception as exc:
        logger.error("Failed to migrate database from %s to %s: %s", source_candidate, abs_path, exc, exc_info=True)
        raise RuntimeError(f"Database migration from '{source_candidate}' to '{abs_path}' failed: {exc}") from exc
    finally:
        cleanup_temp_db_files(dest_tmp_path)

# SQLite connection args for multi-threaded FastAPI handlers
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    ensure_sqlite_directory(settings.DATABASE_URL)
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
