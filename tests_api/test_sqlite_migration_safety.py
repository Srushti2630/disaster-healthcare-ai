"""
Phase 3D-4: Automated Safety and Concurrency Test Suite for SQLite Database Migration.

Validates all 13 safety conditions required by Phase 3D-4:
1. Successful migration from an existing source database.
2. Preservation of existing rows and schema.
3. WAL-mode migration with committed transactions still in the WAL.
4. Verification that migrated data includes those committed transactions.
5. Existing valid destination is never overwritten.
6. Existing corrupt destination causes a safe failure.
7. Failed backup does not leave a partial final destination.
8. Temporary files are cleaned up after failure.
9. Repeated invocation is idempotent.
10. Missing source candidate preserves normal fresh-database initialization.
11. Source database remains intact after successful migration.
12. A publication race does not overwrite a destination created by another process.
13. Permission or backup errors fail safely instead of silently initializing an empty database.
"""
import os
import sqlite3
import pytest

from api.database import ensure_sqlite_directory, check_sqlite_integrity

def test_01_successful_migration_and_row_schema_preservation(tmp_path):
    """Verify that a source database with tables and rows is fully migrated and source is preserved."""
    src_db = tmp_path / "source.db"
    dest_dir = tmp_path / "dest_dir"
    dest_db = dest_dir / "target.db"

    # Create source DB with schema and sample records
    conn = sqlite3.connect(str(src_db))
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, role TEXT)")
    conn.execute("INSERT INTO users VALUES (1, 'officer1@example.com', 'coordinator')")
    conn.execute("INSERT INTO users VALUES (2, 'admin1@example.com', 'admin')")
    conn.commit()
    conn.close()

    # Record source file size and modification time
    orig_src_bytes = src_db.read_bytes()

    # Execute migration
    ensure_sqlite_directory(f"sqlite:///{dest_db}", candidate_sources=[str(src_db)])

    # Verify destination was created and contains exact rows
    assert dest_db.exists()
    assert check_sqlite_integrity(str(dest_db)) is True

    chk_conn = sqlite3.connect(str(dest_db))
    rows = chk_conn.execute("SELECT id, email, role FROM users ORDER BY id").fetchall()
    chk_conn.close()
    assert rows == [
        (1, "officer1@example.com", "coordinator"),
        (2, "admin1@example.com", "admin")
    ]

    # Verify source database file was not modified or deleted
    assert src_db.exists()
    assert src_db.read_bytes() == orig_src_bytes

def test_02_wal_mode_migration_preserves_uncheckpointed_transactions(tmp_path):
    """
    Deliberately configure a source database in WAL mode with wal_autocheckpoint=0.
    Commit records into the WAL, verify uncheckpointed WAL bytes exist, and verify
    that sqlite3.Connection.backup() migrates those committed transactions.
    """
    src_db = tmp_path / "wal_source.db"
    wal_file = tmp_path / "wal_source.db-wal"
    dest_dir = tmp_path / "dest_wal"
    dest_db = dest_dir / "target_wal.db"

    # 1. Initialize DB in WAL mode and disable automatic checkpointing
    conn = sqlite3.connect(str(src_db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute("CREATE TABLE inventory (item TEXT, quantity INT)")
    conn.commit()

    # Checkpoint baseline table structure
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    # 2. Insert rows and commit while autocheckpoint is disabled
    conn.execute("INSERT INTO inventory VALUES ('Beds', 250)")
    conn.execute("INSERT INTO inventory VALUES ('Oxygen', 120)")
    conn.commit()

    # Verify WAL file exists and holds uncheckpointed committed frames
    assert wal_file.exists(), "Source WAL companion file must exist"
    assert wal_file.stat().st_size > 0, "Source WAL must contain uncheckpointed bytes"

    # Confirm that a raw read of the main file without WAL would omit the rows
    # (By opening a raw copy of just the main file)
    raw_copy = tmp_path / "raw_copy.db"
    raw_copy.write_bytes(src_db.read_bytes())
    raw_conn = sqlite3.connect(str(raw_copy))
    raw_rows = raw_conn.execute("SELECT item, quantity FROM inventory").fetchall()
    raw_conn.close()
    assert raw_rows == [], "Raw file copy without WAL should NOT contain the uncheckpointed rows"

    # 3. Perform migration via ensure_sqlite_directory using SQLite Backup API
    ensure_sqlite_directory(f"sqlite:///{dest_db}", candidate_sources=[str(src_db)])
    conn.close()

    # 4. Verify migrated destination database contains all committed transactions from WAL
    assert dest_db.exists()
    assert check_sqlite_integrity(str(dest_db)) is True

    migrated_conn = sqlite3.connect(str(dest_db))
    migrated_rows = migrated_conn.execute("SELECT item, quantity FROM inventory ORDER BY item").fetchall()
    migrated_conn.close()
    assert migrated_rows == [("Beds", 250), ("Oxygen", 120)], "Migrated DB must include all committed WAL rows"

def test_03_existing_valid_destination_is_never_overwritten(tmp_path):
    """Verify that an existing valid destination database is never overwritten by a source candidate."""
    src_db = tmp_path / "src_different.db"
    dest_db = tmp_path / "existing_dest.db"

    # Create destination with data
    d_conn = sqlite3.connect(str(dest_db))
    d_conn.execute("CREATE TABLE status (tag TEXT)")
    d_conn.execute("INSERT INTO status VALUES ('original_destination_content')")
    d_conn.commit()
    d_conn.close()
    dest_bytes = dest_db.read_bytes()

    # Create source with different data
    s_conn = sqlite3.connect(str(src_db))
    s_conn.execute("CREATE TABLE status (tag TEXT)")
    s_conn.execute("INSERT INTO status VALUES ('new_source_content')")
    s_conn.commit()
    s_conn.close()

    # Call ensure_sqlite_directory
    ensure_sqlite_directory(f"sqlite:///{dest_db}", candidate_sources=[str(src_db)])

    # Verify destination was NOT modified
    assert dest_db.read_bytes() == dest_bytes
    chk_conn = sqlite3.connect(str(dest_db))
    rows = chk_conn.execute("SELECT tag FROM status").fetchall()
    chk_conn.close()
    assert rows == [("original_destination_content",)]

def test_04_existing_corrupt_destination_causes_safe_failure(tmp_path):
    """Verify that an existing corrupt or truncated destination file raises RuntimeError and fails safe."""
    dest_db = tmp_path / "corrupt_dest.db"
    src_db = tmp_path / "valid_src.db"

    # Write invalid corrupted garbage bytes to destination
    dest_db.write_bytes(b"SQLite format 3\x00corrupted garbage data block" * 8)

    # Valid source
    s_conn = sqlite3.connect(str(src_db))
    s_conn.execute("CREATE TABLE t (x INT)")
    s_conn.commit()
    s_conn.close()

    with pytest.raises(RuntimeError, match="failed integrity verification"):
        ensure_sqlite_directory(f"sqlite:///{dest_db}", candidate_sources=[str(src_db)])

def test_05_failed_backup_does_not_leave_partial_destination(tmp_path, monkeypatch):
    """Verify that if backup fails during execution, no partial target file is published and temp is removed."""
    src_db = tmp_path / "source_for_fail.db"
    dest_dir = tmp_path / "dest_fail_dir"
    dest_db = dest_dir / "target_fail.db"

    s_conn = sqlite3.connect(str(src_db))
    s_conn.execute("CREATE TABLE t (x INT)")
    s_conn.commit()
    s_conn.close()

    # Inject failure into backup via monkeypatching sqlite3.connect factory in api.database
    real_connect = sqlite3.connect

    class FaultyConn(sqlite3.Connection):
        def backup(self, *a, **k):
            raise sqlite3.OperationalError("Simulated I/O disk error during backup stream")

    def mock_connect(*args, **kwargs):
        return real_connect(*args, **kwargs, factory=FaultyConn)

    monkeypatch.setattr("api.database.sqlite3.connect", mock_connect)

    with pytest.raises(RuntimeError, match="Simulated I/O disk error"):
        ensure_sqlite_directory(f"sqlite:///{dest_db}", candidate_sources=[str(src_db)])

    # Verify final destination was not created
    assert not dest_db.exists(), "Final destination must not exist after failed backup"

    # Verify no temporary backup files left in destination directory
    temp_files = [f for f in os.listdir(dest_dir) if f.startswith(".migrating_")]
    assert temp_files == [], f"Temporary files must be cleaned up on failure: {temp_files}"

def test_06_temporary_files_cleaned_up_on_integrity_check_failure(tmp_path, monkeypatch):
    """Verify that if integrity check fails on temporary backup, it is unlinked and error is raised."""
    src_db = tmp_path / "source_integrity_fail.db"
    dest_dir = tmp_path / "dest_int_fail_dir"
    dest_db = dest_dir / "target_int_fail.db"

    s_conn = sqlite3.connect(str(src_db))
    s_conn.execute("CREATE TABLE t (x INT)")
    s_conn.commit()
    s_conn.close()

    # Monkeypatch check_sqlite_integrity to fail on the temporary file
    real_check = check_sqlite_integrity
    def mock_check(p):
        if ".migrating_" in p:
            return False
        return real_check(p)

    monkeypatch.setattr("api.database.check_sqlite_integrity", mock_check)

    with pytest.raises(RuntimeError, match="Integrity check failed"):
        ensure_sqlite_directory(f"sqlite:///{dest_db}", candidate_sources=[str(src_db)])

    assert not dest_db.exists()
    temp_files = [f for f in os.listdir(dest_dir) if f.startswith(".migrating_")]
    assert temp_files == []

def test_07_repeated_invocation_is_idempotent(tmp_path):
    """Verify that multiple consecutive invocations succeed without error or state change."""
    src_db = tmp_path / "source_idempotent.db"
    dest_db = tmp_path / "dest_idempotent.db"

    s_conn = sqlite3.connect(str(src_db))
    s_conn.execute("CREATE TABLE sample (id INT)")
    s_conn.execute("INSERT INTO sample VALUES (42)")
    s_conn.commit()
    s_conn.close()

    db_url = f"sqlite:///{dest_db}"
    # Invocation 1
    ensure_sqlite_directory(db_url, candidate_sources=[str(src_db)])
    assert dest_db.exists()

    # Invocations 2 and 3
    ensure_sqlite_directory(db_url, candidate_sources=[str(src_db)])
    ensure_sqlite_directory(db_url, candidate_sources=[str(src_db)])

    chk_conn = sqlite3.connect(str(dest_db))
    rows = chk_conn.execute("SELECT id FROM sample").fetchall()
    chk_conn.close()
    assert rows == [(42,)]

def test_08_missing_source_candidate_allows_fresh_initialization(tmp_path):
    """Verify that if no source candidates exist, it returns cleanly for fresh DB initialization."""
    dest_db = tmp_path / "fresh_app.db"
    non_existent_source = str(tmp_path / "non_existent.db")

    # Call ensure_sqlite_directory with no existing candidates
    ensure_sqlite_directory(f"sqlite:///{dest_db}", candidate_sources=[non_existent_source])

    # Destination is not created yet; init_db will create it
    assert not dest_db.exists()

def test_09_source_database_remains_intact_after_migration(tmp_path):
    """Verify that source database file is identical before and after migration."""
    src_db = tmp_path / "src_intact.db"
    dest_db = tmp_path / "dest_intact.db"

    s_conn = sqlite3.connect(str(src_db))
    s_conn.execute("CREATE TABLE items (val TEXT)")
    s_conn.execute("INSERT INTO items VALUES ('alpha'), ('beta')")
    s_conn.commit()
    s_conn.close()

    src_before = src_db.read_bytes()
    ensure_sqlite_directory(f"sqlite:///{dest_db}", candidate_sources=[str(src_db)])
    src_after = src_db.read_bytes()

    assert src_before == src_after

def test_10_publication_race_does_not_overwrite_concurrent_destination(tmp_path, monkeypatch):
    """
    Simulate a concurrency race where another process publishes the destination file
    just before os.link() executes. Verify FileExistsError is caught, the concurrent
    destination is preserved without overwrite, and the temporary file is unlinked.
    """
    src_db = tmp_path / "src_race.db"
    dest_dir = tmp_path / "dest_race_dir"
    dest_db = dest_dir / "target_race.db"

    s_conn = sqlite3.connect(str(src_db))
    s_conn.execute("CREATE TABLE t (val TEXT)")
    s_conn.execute("INSERT INTO t VALUES ('from_source')")
    s_conn.commit()
    s_conn.close()

    # Pre-emptively create a valid concurrent destination right as os.link is called
    def mock_link(src, dst):
        # Simulate competing process publishing target_race.db first
        c_conn = sqlite3.connect(dst)
        c_conn.execute("CREATE TABLE t (val TEXT)")
        c_conn.execute("INSERT INTO t VALUES ('published_by_competing_process')")
        c_conn.commit()
        c_conn.close()
        raise FileExistsError(f"[Errno 17] File exists: '{dst}'")

    monkeypatch.setattr(os, "link", mock_link)

    # Call migration
    ensure_sqlite_directory(f"sqlite:///{dest_db}", candidate_sources=[str(src_db)])

    # Verify competing process content is preserved
    chk_conn = sqlite3.connect(str(dest_db))
    rows = chk_conn.execute("SELECT val FROM t").fetchall()
    chk_conn.close()
    assert rows == [("published_by_competing_process",)], "Concurrent destination must NOT be overwritten"

    # Verify no temp files remain
    temp_files = [f for f in os.listdir(dest_dir) if f.startswith(".migrating_")]
    assert temp_files == []

def test_11_corrupt_source_candidate_fails_safe_without_creating_destination(tmp_path):
    """Verify that if source database candidate is corrupt, migration fails closed without creating destination."""
    src_db = tmp_path / "corrupt_source.db"
    dest_db = tmp_path / "dest_uncreated.db"

    src_db.write_bytes(b"SQLite format 3\x00random non-sqlite junk block" * 10)

    with pytest.raises(RuntimeError, match="failed integrity verification"):
        ensure_sqlite_directory(f"sqlite:///{dest_db}", candidate_sources=[str(src_db)])

    assert not dest_db.exists()

def test_12_permission_or_unreadable_source_fails_closed(tmp_path, monkeypatch):
    """Verify that unreadable source or connection failure raises clear RuntimeError rather than silent empty DB."""
    src_db = tmp_path / "unreadable_source.db"
    dest_db = tmp_path / "dest_unreadable.db"

    s_conn = sqlite3.connect(str(src_db))
    s_conn.execute("CREATE TABLE t (x INT)")
    s_conn.commit()
    s_conn.close()

    def mock_sqlite_connect(*args, **kwargs):
        raise sqlite3.OperationalError("Unable to open database file: permission denied")

    monkeypatch.setattr(sqlite3, "connect", mock_sqlite_connect)

    with pytest.raises(RuntimeError, match="failed integrity verification|Database migration from"):
        ensure_sqlite_directory(f"sqlite:///{dest_db}", candidate_sources=[str(src_db)])

    assert not dest_db.exists()

def test_13_recovery_from_abandoned_stale_temp_files(tmp_path):
    """Verify that stale .migrating_*.tmp files from crashed previous runs are swept without deleting destination."""
    src_db = tmp_path / "src_stale.db"
    dest_dir = tmp_path / "dest_stale_dir"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_db = dest_dir / "target_stale.db"

    # Plant an abandoned stale file
    stale_file = dest_dir / ".migrating_dead1234beef_target_stale.db.tmp"
    stale_file.write_bytes(b"abandoned junk")

    s_conn = sqlite3.connect(str(src_db))
    s_conn.execute("CREATE TABLE t (msg TEXT)")
    s_conn.execute("INSERT INTO t VALUES ('recovered')")
    s_conn.commit()
    s_conn.close()

    ensure_sqlite_directory(f"sqlite:///{dest_db}", candidate_sources=[str(src_db)])

    assert dest_db.exists()
    assert not stale_file.exists(), "Stale migration temporary file must be purged"
    chk_conn = sqlite3.connect(str(dest_db))
    rows = chk_conn.execute("SELECT msg FROM t").fetchall()
    chk_conn.close()
    assert rows == [("recovered",)]
