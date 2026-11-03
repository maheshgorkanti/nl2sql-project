
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().with_name("operations.db")

# Fixed reference time for reproducible sample-data tests.
REFERENCE_NOW = "2026-10-12T12:00:00Z"


def setup_database():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS services (
                service_id TEXT PRIMARY KEY,
                service_name TEXT NOT NULL UNIQUE,
                environment TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY,
                service_id TEXT NOT NULL,
                title TEXT NOT NULL,
                started_at TEXT NOT NULL,
                resolved_at TEXT,
                status TEXT NOT NULL
                    CHECK (status IN ('open', 'resolved')),

                FOREIGN KEY (service_id)
                    REFERENCES services(service_id),

                CHECK (
                    resolved_at IS NULL
                    OR resolved_at >= started_at
                ),

                CHECK (
                    (status = 'open' AND resolved_at IS NULL)
                    OR
                    (status = 'resolved' AND resolved_at IS NOT NULL)
                )
            );

            CREATE TABLE IF NOT EXISTS deployments (
                deployment_id TEXT PRIMARY KEY,
                service_id TEXT NOT NULL,
                deployed_at TEXT NOT NULL,
                version TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK (
                        status IN ('success', 'failed', 'in_progress')
                    ),

                FOREIGN KEY (service_id)
                    REFERENCES services(service_id)
            );

            CREATE TABLE IF NOT EXISTS error_events (
                error_id TEXT PRIMARY KEY,
                service_id TEXT NOT NULL,
                incident_id TEXT,
                timestamp TEXT NOT NULL,
                error_message TEXT NOT NULL,
                severity TEXT NOT NULL
                    CHECK (
                        severity IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL')
                    ),

                FOREIGN KEY (service_id)
                    REFERENCES services(service_id),

                FOREIGN KEY (incident_id)
                    REFERENCES incidents(incident_id)
            );

            CREATE INDEX IF NOT EXISTS
                idx_errors_service_timestamp
            ON error_events(service_id, timestamp);

            CREATE INDEX IF NOT EXISTS
                idx_errors_incident
            ON error_events(incident_id);

            CREATE INDEX IF NOT EXISTS
                idx_deployments_service_timestamp
            ON deployments(service_id, deployed_at);

            CREATE INDEX IF NOT EXISTS
                idx_incidents_service_started
            ON incidents(service_id, started_at);
        """)

        # Seed only a new, empty operational dataset.
        # Never delete existing data or silently reseed it.
        existing_services = conn.execute(
            "SELECT COUNT(*) FROM services"
        ).fetchone()[0]

        if existing_services == 0:
            conn.executemany(
                """
                INSERT INTO services
                    (service_id, service_name, environment)
                VALUES (?, ?, ?)
                """,
                [
                    ("SVC-001", "payments-api", "production"),
                    ("SVC-002", "orders-api", "production"),
                    ("SVC-003", "auth-api", "staging"),
                ],
            )

            conn.executemany(
                """
                INSERT INTO incidents
                    (
                        incident_id, service_id, title,
                        started_at, resolved_at, status
                    )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "INC-100",
                        "SVC-001",
                        "Payment API timeout spike",
                        "2026-10-12T10:10:00Z",
                        None,
                        "open",
                    ),
                    (
                        "INC-101",
                        "SVC-002",
                        "Order processing failures",
                        "2026-10-11T14:15:00Z",
                        "2026-10-11T15:10:00Z",
                        "resolved",
                    ),
                ],
            )

            conn.executemany(
                """
                INSERT INTO deployments
                    (
                        deployment_id, service_id,
                        deployed_at, version, status
                    )
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        "DEP-001",
                        "SVC-001",
                        "2026-10-12T10:00:00Z",
                        "2.4.1",
                        "success",
                    ),
                    (
                        "DEP-002",
                        "SVC-002",
                        "2026-10-11T14:00:00Z",
                        "1.8.0",
                        "success",
                    ),
                    (
                        "DEP-003",
                        "SVC-003",
                        "2026-10-12T09:30:00Z",
                        "3.1.0",
                        "failed",
                    ),
                ],
            )

            conn.executemany(
                """
                INSERT INTO error_events
                    (
                        error_id, service_id, incident_id,
                        timestamp, error_message, severity
                    )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "ERR-001", "SVC-001", None,
                        "2026-10-12T09:05:00Z",
                        "Payment request timeout",
                        "ERROR",
                    ),
                    (
                        "ERR-002", "SVC-001", None,
                        "2026-10-12T09:25:00Z",
                        "Payment gateway timeout",
                        "ERROR",
                    ),
                    (
                        "ERR-003", "SVC-001", "INC-100",
                        "2026-10-12T10:10:00Z",
                        "HTTP 504 from payment gateway",
                        "CRITICAL",
                    ),
                    (
                        "ERR-004", "SVC-001", "INC-100",
                        "2026-10-12T10:15:00Z",
                        "Connection pool timeout",
                        "ERROR",
                    ),
                    (
                        "ERR-005", "SVC-001", "INC-100",
                        "2026-10-12T10:35:00Z",
                        "Database connection pool exhausted",
                        "CRITICAL",
                    ),
                    (
                        "ERR-006", "SVC-001", "INC-100",
                        "2026-10-12T10:50:00Z",
                        "HTTP 504 from payment gateway",
                        "ERROR",
                    ),
                    (
                        "ERR-007", "SVC-002", "INC-101",
                        "2026-10-11T14:15:00Z",
                        "Order processing failed",
                        "ERROR",
                    ),
                    (
                        "ERR-008", "SVC-003", None,
                        "2026-10-12T09:35:00Z",
                        "Authentication request failed",
                        "WARNING",
                    ),
                ],
            )

    print(f"Operational database ready: {DB_PATH}")
    print(f"Fixed reference time: {REFERENCE_NOW}")


if __name__ == "__main__":
    setup_database()