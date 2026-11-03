from pathlib import Path
import hashlib
import shutil
import sqlite3

BASE_DIR = Path(__file__).resolve().parent
SOURCE_DB = BASE_DIR / "operations.db"
TARGET_DB = BASE_DIR / "operations_v2.db"

ERROR_FIXTURES = [
    (
        "ERR-009",
        "SVC-001",
        None,
        "2026-10-11T11:59:59Z",
        "Pre-window test event",
        "ERROR",
    ),
    (
        "ERR-010",
        "SVC-003",
        None,
        "2026-10-11T12:00:00Z",
        "Window-start boundary test event",
        "WARNING",
    ),
    (
        "ERR-011",
        "SVC-002",
        None,
        "2026-10-12T12:00:00Z",
        "Window-end boundary test event",
        "ERROR",
    ),
]

INCIDENT_FIXTURES = [
    (
        "INC-102",
        "SVC-003",
        "Window-start boundary test incident",
        "2026-10-11T12:00:00Z",
        None,
        "open",
    ),
    (
        "INC-103",
        "SVC-001",
        "Pre-window incident resolved inside window",
        "2026-10-11T11:59:59Z",
        "2026-10-11T12:30:00Z",
        "resolved",
    ),
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    if not SOURCE_DB.is_file():
        raise FileNotFoundError(f"Source database not found: {SOURCE_DB}")

    if SOURCE_DB.resolve() == TARGET_DB.resolve():
        raise RuntimeError("Source and target paths must be different.")

    source_hash_before = sha256_file(SOURCE_DB)

    # Rebuild only the v2 copy. The source database is never opened for writes.
    if TARGET_DB.exists():
        TARGET_DB.unlink()

    shutil.copy2(SOURCE_DB, TARGET_DB)

    with sqlite3.connect(TARGET_DB) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        required_tables = {
            "services", "incidents", "deployments", "error_events"
        }
        missing = required_tables - tables
        if missing:
            raise RuntimeError(f"Missing required tables: {sorted(missing)}")

        # Confirm all fixture service IDs exist before inserting.
        known_services = {
            row[0] for row in conn.execute("SELECT service_id FROM services")
        }
        fixture_services = {
            row[1] for row in ERROR_FIXTURES
        } | {
            row[1] for row in INCIDENT_FIXTURES
        }
        unknown_services = fixture_services - known_services
        if unknown_services:
            raise RuntimeError(
                f"Fixture references unknown services: {sorted(unknown_services)}"
            )

        # One transaction: either all fixtures are inserted, or none are.
        with conn:
            conn.executemany(
                """
                INSERT INTO error_events
                    (error_id, service_id, incident_id,
                     timestamp, error_message, severity)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ERROR_FIXTURES,
            )

            conn.executemany(
                """
                INSERT INTO incidents
                    (incident_id, service_id, title,
                     started_at, resolved_at, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                INCIDENT_FIXTURES,
            )

            violations = conn.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

            if violations:
                raise RuntimeError(
                    f"Foreign-key violations; fixture transaction aborted: "
                    f"{violations}"
                )

        counts = {
            table: conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            for table in sorted(required_tables)
        }

        fk_violations_after_commit = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if fk_violations_after_commit:
            raise RuntimeError(
                f"Foreign-key check failed: {fk_violations_after_commit}"
            )

    source_hash_after = sha256_file(SOURCE_DB)
    if source_hash_before != source_hash_after:
        raise RuntimeError(
            "Source operations.db hash changed unexpectedly. Investigate."
        )

    print(f"Source database: {SOURCE_DB}")
    print(f"V2 database:    {TARGET_DB}")
    print("Fixture inserts: 3 error events, 2 incidents")
    print("Table row counts:", counts)
    print("Foreign-key check: PASS (no violations)")
    print("Source hash unchanged: PASS")
    print("Setup complete. Local results are now available for verification.")


if __name__ == "__main__":
    main()