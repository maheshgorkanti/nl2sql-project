# 🚀 NL2SQL System using Vanna AI + FastAPI

## Project Overview

This project is a **Natural Language to SQL (NL2SQL) system** that allows users to query a database using plain English instead of writing SQL queries.

The system translates user questions into SQL queries and executes them on a database, returning structured results via a REST API.

This solution is designed to simplify data access for non-technical users and improve productivity in data-driven environments.

## Tech Stack

- Python
- FastAPI (Backend API)
- SQLite (Database)
- Vanna AI 2.0 (NL → SQL generation)
- Pandas (Data handling)

## How It Works

1. User sends a question in plain English  
   Example: *"Top 3 customers by total spending"*

2. System processes the question:
   - First tries to generate SQL using **Vanna AI**
   - If AI fails, uses a **rule-based fallback system**

3. Generated SQL is:
   - Validated (only SELECT queries allowed)
   - Executed on SQLite database

4. API returns:
   - Generated SQL
   - Query results
   - Execution time
   - Row count
   - Status message

## System Flow

User Input → NL Processing → SQL Generation → SQL Validation → Database Execution → JSON Response

## Example Input & Output

### 🔹 Input

GET /query?question=Total sales

### 🔹 Output

```json
{
  "question": "Total sales",
  "sql": "SELECT SUM(amount) AS total_sales FROM orders;",
  "result": [
    {
      "total_sales": 12900
    }
  ],
  "execution_time": 0.0048,
  "row_count": 1,
  "message": "Query executed successfully"
}