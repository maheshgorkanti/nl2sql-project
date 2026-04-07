import pandas as pd
import sqlite3

def rule_based_sql(question):
    q = question.lower()

    if "top" in q and "customer" in q:
        return """
        SELECT customer_name, SUM(amount) AS total_spent
        FROM orders
        GROUP BY customer_name
        ORDER BY total_spent DESC
        LIMIT 3;
        """

    elif "total sales" in q:
        return "SELECT SUM(amount) AS total_sales FROM orders;"

    elif "average" in q:
        return "SELECT AVG(amount) AS avg_order_value FROM orders;"

    elif "count" in q or "number of orders" in q:
        return "SELECT COUNT(*) AS total_orders FROM orders;"

    elif "highest" in q:
        return "SELECT MAX(amount) AS highest_order FROM orders;"

    else:
        return "SELECT * FROM orders LIMIT 5;"


try:
    from vanna.chromadb.chromadb_vector import ChromaDB_VectorStore

    class MyVanna(ChromaDB_VectorStore):
        def __init__(self):
            super().__init__()

    vn = MyVanna()

    vn.train("""
    Table: orders
    Columns:
    - order_id
    - customer_name
    - amount

    Examples:

    Question: Total sales
    SQL: SELECT SUM(amount) AS total_sales FROM orders;

    Question: Top 3 customers by total spending
    SQL:
    SELECT customer_name, SUM(amount) AS total_spent
    FROM orders
    GROUP BY customer_name
    ORDER BY total_spent DESC
    LIMIT 3;

    Question: Average order value
    SQL: SELECT AVG(amount) AS avg_order_value FROM orders;
    """)

    def generate_sql(question):
        try:
            sql = vn.generate_sql(question)

            if not sql or "select" not in sql.lower():
                return rule_based_sql(question)

            return sql

        except Exception as e:
            print("Vanna failed, using fallback:", e)
            return rule_based_sql(question)

except:
    def generate_sql(question):
        return rule_based_sql(question)


def run_sql(sql):
    conn = sqlite3.connect("company.db")

    try:
        if any(word in sql.lower() for word in ["delete", "drop", "update", "insert"]):
            return {"error": "Only SELECT queries are allowed"}

        df = pd.read_sql_query(sql, conn)
        return df.to_dict(orient="records")

    except Exception as e:
        return {"error": str(e)}

    finally:
        conn.close()