
import logging
import time

from fastapi import FastAPI, HTTPException

from sql_engine import generate_sql, run_sql
from operational_query_engine import answer_operational_question

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()


@app.get("/")
def home():
    return {"message": "NL2SQL API Running"}


@app.get("/query")
def query(question: str):
    question = question.strip()

    if not question:
        raise HTTPException(
            status_code=422,
            detail="Please provide a question."
        )

    sql = generate_sql(question)

    if sql is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "unsupported_question",
                "message": (
                    "This question is not supported by the current "
                    "query patterns and database schema."
                ),
                "supported_examples": [
                    "Total sales",
                    "Top 3 customers by total spending",
                    "Average order value",
                    "Number of orders",
                    "Highest order amount",
                ],
            },
        )

    logger.info("Question: %s", question)
    logger.info("Generated SQL: %s", sql)

    start = time.perf_counter()
    result = run_sql(sql)
    execution_time = round(time.perf_counter() - start, 4)

    if isinstance(result, dict) and "error" in result:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "query_execution_failed",
                "message": result["error"],
            },
        )

    return {
        "question": question,
        "sql": sql,
        "result": result,
        "execution_time": execution_time,
        "row_count": len(result),
        "status": "success",
        "message": (
            "Query executed successfully"
            if result
            else "Query executed successfully; no matching records"
        ),
    }


@app.get("/operational-query")
def operational_query(question: str):
    question = question.strip()

    if not question:
        raise HTTPException(
            status_code=422,
            detail="Please provide a question."
        )

    logger.info("Operational question: %s", question)

    try:
        result = answer_operational_question(question)
    except Exception:
        logger.exception("Operational query failed")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "operational_query_failed",
                "message": "The operational query could not be completed."
            }
        )

    return {
        "question": question,
        **result
    }
