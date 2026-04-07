import time
import logging
logging.basicConfig(level=logging.INFO)
from fastapi import FastAPI
import sqlite3
import pandas as pd
from sql_engine import generate_sql, run_sql


app = FastAPI()

conn = sqlite3.connect("company.db", check_same_thread=False)

@app.get("/")
def home():
    return {"message": "NL2SQL API Running 🚀"}

@app.get("/query")
def query(question: str):
    try:
        sql = generate_sql(question)

        logging.info(f"Question: {question}")
        logging.info(f"Generated SQL: {sql}")

        start = time.time()
        result = run_sql(sql)
        end = time.time()

        execution_time = round(end - start, 4)

        if isinstance(result, list):
            row_count = len(result)
            message = "Query executed successfully"
        elif isinstance(result, dict) and "error" in result:
            row_count = 0
            message = "Query failed"
        else:
            row_count = 0
            message = "Query executed, but unexpected result type"

        return {
            "question": question,
            "sql": sql,
            "result": result,
            "execution_time": execution_time,
            "row_count": row_count,
            "message": message
        }


    except Exception as e:
        logging.error(f"Exception while executing query: {str(e)}")
        return {"error": str(e)}