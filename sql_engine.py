
import logging
import sqlite3
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().with_name("company.db")


def rule_based_sql(question: str) -> str | None:
    """Generate SQL only for explicitly supported question patterns."""
    q = " ".join(question.lower().strip().rstrip("?.!").split())

    if (
        "top" in q
        and "customer" in q
        and any(word in q for word in ("spending", "spent", "sales"))
    ):
        return """
            SELECT customer_name, SUM(amount) AS total_spent
            FROM orders
            GROUP BY customer_name
            ORDER BY total_spent DESC
            LIMIT 3;
        """

    if "total sales" in q:
        return "SELECT SUM(amount) AS total_sales FROM orders;"

    if any(phrase in q for phrase in (
        "average order value",
        "average order amount",
    )):
        return "SELECT AVG(amount) AS avg_order_value FROM orders;"

    if (
        ("count" in q or "number of" in q)
        and "order" in q
    ):
        return "SELECT COUNT(*) AS total_orders FROM orders;"

    if "highest" in q and "order" in q:
        return "SELECT MAX(amount) AS highest_order FROM orders;"

    return None


def generate_sql(question: str) -> str | None:
    """Use the verified, deterministic baseline."""
    return rule_based_sql(question)


def run_sql(sql: str) -> list[dict] | dict:
    """Execute one read-only SQL query against the existing database."""
    if not isinstance(sql, str) or not sql.strip():
        return {"error": "SQL query must not be empty"}

    try:
        # Open the database in read-only mode.
        db_uri = DB_PATH.as_uri() + "?mode=ro"

        with sqlite3.connect(db_uri, uri=True) as conn:
            # Permit reading and SELECT operations only.
            allowed_actions = {
                sqlite3.SQLITE_SELECT,
                sqlite3.SQLITE_READ,
                sqlite3.SQLITE_FUNCTION,
            }

            if hasattr(sqlite3, "SQLITE_RECURSIVE"):
                allowed_actions.add(sqlite3.SQLITE_RECURSIVE)

            def authorize(action, arg1, arg2, database, trigger):
                if action in allowed_actions:
                    return sqlite3.SQLITE_OK
                return sqlite3.SQLITE_DENY

            conn.set_authorizer(authorize)

            df = pd.read_sql_query(sql, conn)
            return df.to_dict(orient="records")


    except pd.errors.DatabaseError as e:
        logger.warning("SQL query rejected or failed: %s", e)
        return {"error": "Query rejected by read-only policy or query failed"}

    except sqlite3.DatabaseError as e:
        logger.warning("SQL query rejected or failed: %s", e)
        return {"error": "Query rejected by read-only policy or query failed"}

    except Exception:
        logger.exception("Unexpected SQL execution failure")
        return {"error": "Unexpected query execution failure"}