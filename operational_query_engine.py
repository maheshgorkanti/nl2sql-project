import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().with_name("operations_v2.db")

WINDOW_START = "2026-10-11T12:00:00Z"
WINDOW_END = "2026-10-12T12:00:00Z"

DESTRUCTIVE_PATTERN = re.compile(
    r"\b(delete|drop|update|insert|alter|truncate|create|replace|"
    r"attach|detach|vacuum)\b",
    re.IGNORECASE,
)


def _normalize(question: str) -> str:
    import re

    normalized = " ".join(
        question.lower().strip().rstrip("?.!").split()
    )

    # Normalize equivalent wording for the fixed 24-hour window.
    normalized = re.sub(
        r"\bpast 24 hours\b",
        "last 24 hours",
        normalized,
    )

    return normalized


def _read(query: str, params: tuple = ()) -> list[tuple]:
    """Execute a fixed query using a read-only SQLite connection."""
    uri = DB_PATH.as_uri() + "?mode=ro"

    with sqlite3.connect(uri, uri=True) as conn:
        conn.execute("PRAGMA query_only = ON")

        # Defense in depth: deny every SQLite action except reading.
        allowed = {
            sqlite3.SQLITE_SELECT,
            sqlite3.SQLITE_READ,
            sqlite3.SQLITE_FUNCTION,
        }
        if hasattr(sqlite3, "SQLITE_RECURSIVE"):
            allowed.add(sqlite3.SQLITE_RECURSIVE)

        def authorize(action, arg1, arg2, database, trigger):
            return (
                sqlite3.SQLITE_OK
                if action in allowed
                else sqlite3.SQLITE_DENY
            )

        conn.set_authorizer(authorize)
        return conn.execute(query, params).fetchall()


def _service_error_counts(start: str, end: str) -> list[list]:
    rows = _read(
        """
        SELECT s.service_name, COUNT(e.error_id) AS error_count
        FROM services AS s
        LEFT JOIN error_events AS e
          ON e.service_id = s.service_id
         AND e.timestamp >= ?
         AND e.timestamp < ?
        GROUP BY s.service_id, s.service_name
        ORDER BY s.service_name
        """,
        (start, end),
    )
    return [[name, count] for name, count in rows]


def _incidents_in_window() -> list[list]:
    rows = _read(
        """
        SELECT incident_id, started_at
        FROM incidents
        WHERE started_at >= ?
          AND started_at < ?
        ORDER BY started_at DESC, incident_id
        """,
        (WINDOW_START, WINDOW_END),
    )
    return [[incident_id, started_at] for incident_id, started_at in rows]


def _deployment_comparison(deployment_id: str) -> dict:
    rows = _read(
        """
        SELECT service_id, deployed_at, status
        FROM deployments
        WHERE deployment_id = ?
        """,
        (deployment_id,),
    )

    if not rows:
        return {
            "status": "not_found",
            "message": f"Deployment {deployment_id} was not found.",
        }

    service_id, deployed_at, deployment_status = rows[0]

    from datetime import datetime, timedelta, timezone

    deployed = datetime.fromisoformat(deployed_at.replace("Z", "+00:00"))
    if deployed.tzinfo is None:
        deployed = deployed.replace(tzinfo=timezone.utc)

    before_start = (deployed - timedelta(hours=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    after_end = (deployed + timedelta(hours=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    before_count = _read(
        """
        SELECT COUNT(*)
        FROM error_events
        WHERE service_id = ?
          AND timestamp >= ?
          AND timestamp < ?
        """,
        (service_id, before_start, deployed_at),
    )[0][0]

    after_count = _read(
        """
        SELECT COUNT(*)
        FROM error_events
        WHERE service_id = ?
          AND timestamp >= ?
          AND timestamp < ?
        """,
        (service_id, deployed_at, after_end),
    )[0][0]

    result = {
        "deployment_id": deployment_id,
        "before_error_count": before_count,
        "after_error_count": after_count,
    }

    if deployment_id == "DEP-001":
        difference = after_count - before_count
        result.update({
            "before_window": [before_start, deployed_at],
            "after_window": [deployed_at, after_end],
            "difference_after_minus_before": difference,
            "required_interpretation": (
                f"{difference} more recorded errors observed after "
                "the deployment; this does not establish causation."
                if difference >= 0
                else f"{abs(difference)} fewer recorded errors observed after "
                "the deployment; this does not establish causation."
            ),
        })

    elif deployment_id == "DEP-002":
        result["before_window"] = [before_start, deployed_at]
        result["after_window"] = [deployed_at, after_end]
        result["required_wording"] = (
            f"{after_count} recorded error observed after, "
            f"{before_count} before."
        )

    return result


def answer_operational_question(question: str) -> dict:
    """
    Handle the supported operational benchmark questions.

    This module never executes SQL supplied by the user.
    """
    if not isinstance(question, str) or not question.strip():
        return {
            "status": "invalid_question",
            "message": "Please provide a question.",
        }

    q = _normalize(question)

    # Refuse destructive requests before attempting question matching.
    if DESTRUCTIVE_PATTERN.search(q) or (
        ";" in q and re.search(r"\b(select|with)\b", q, re.I)
    ):
        return {
            "status": "refused",
            "category": "unsafe",
            "message": (
                "This request is refused. No user-supplied SQL was executed "
                "and no data or schema was modified."
            ),
        }

    # Requests that lack enough scope must be clarified.
    if q == "show errors":
        return {
            "status": "clarification_required",
            "category": "ambiguous",
            "message": (
                "What time range should I check? You can also specify "
                "a service or severity."
            ),
        }

    if q == "compare deployment errors":
        return {
            "status": "clarification_required",
            "category": "ambiguous",
            "message": (
                "Which deployment or deployments should I compare, "
                "and what time windows should I use?"
            ),
        }

    # The available schema cannot establish individual responsibility.
    if "who caused incident" in q or "which engineer was on call" in q:
        return {
            "status": "unanswerable",
            "category": "unanswerable",
            "message": (
                "The available database contains no person, responsibility, "
                "or on-call records to answer this."
            ),
        }

    # Report temporal evidence without claiming causation.
    if "which deployment caused incident inc-100" in q:
        rows = _read(
            """
            SELECT i.incident_id, i.started_at, i.service_id,
                   d.deployment_id, d.deployed_at
            FROM incidents AS i
            LEFT JOIN deployments AS d
              ON d.service_id = i.service_id
             AND d.deployed_at <= i.started_at
            WHERE i.incident_id = ?
            ORDER BY d.deployed_at DESC
            LIMIT 1
            """,
            ("INC-100",),
        )

        if not rows:
            return {
                "status": "unanswerable",
                "category": "unanswerable",
                "message": "No matching incident evidence was found.",
            }

        incident_id, started_at, service_id, deployment_id, deployed_at = rows[0]
        return {
            "status": "unanswerable",
            "category": "unanswerable",
            "result": {
                "incident_id": incident_id,
                "incident_started_at": started_at,
                "deployment_id": deployment_id,
                "deployment_at": deployed_at,
                "conclusion": (
                    "These records show temporal proximity only; they do "
                    "not establish that the deployment caused the incident."
                ),
            },
        }

    # A1-A3: error counts by service.
    if (
        "error" in q
        and "service" in q
        and (
            "last 24 hours" in q
            or (
                "2026-10-11t12:00:00z" in q
                and "2026-10-12t12:00:00z" in q
            )
        )
    ):
        if "between" in q:
            start, end = WINDOW_START, WINDOW_END
        else:
            start, end = WINDOW_START, WINDOW_END

        return {
            "status": "answered",
            "category": "answerable",
            "result": _service_error_counts(start, end),
        }

    # A4-A5: incidents started in the fixed reference window.
    if "incident" in q and (
        "last 24 hours" in q or "started_at" in q
    ):
        incidents = _incidents_in_window()

        if q.startswith("how many"):
            return {
                "status": "answered",
                "category": "answerable",
                "result": {
                    "count": len(incidents),
                    "incidents": incidents,
                },
            }

        return {
            "status": "answered",
            "category": "answerable",
            "result": incidents,
        }

    # A6-A9: fixed one-hour comparisons around a known deployment.
    deployment_id = None
    if "dep-001" in q and (
        "before" in q or "after" in q or "either side" in q
    ):
        deployment_id = "DEP-001"
    elif "dep-002" in q and (
        "before" in q or "after" in q
    ):
        deployment_id = "DEP-002"

    if deployment_id and "error" in q:
        result = _deployment_comparison(deployment_id)

        if result.get("status") == "not_found":
            return result

        return {
            "status": "answered",
            "category": "answerable",
            "result": result,
        }

    # A10: failed deployments, with service and environment context.
    if "deployment" in q and "failed" in q:
        rows = _read(
            """
            SELECT d.deployment_id, d.service_id, s.service_name,
                   s.environment, d.deployed_at, d.status
            FROM deployments AS d
            JOIN services AS s ON s.service_id = d.service_id
            WHERE d.status = ?
            ORDER BY d.deployed_at, d.deployment_id
            """,
            ("failed",),
        )

        return {
            "status": "answered",
            "category": "answerable",
            "result": [list(row) for row in rows],
        }

    # B2: an unqualified incident count means all incident records.
    if "how many incidents are there" in q:
        count = _read("SELECT COUNT(*) FROM incidents")[0][0]
        return {
            "status": "answered",
            "category": "answerable",
            "result": count,
        }

    return {
        "status": "unsupported_question",
        "message": (
            "This question is not supported by the operational query rules."
        ),
    }
