import sqlite3

conn = sqlite3.connect("company.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    customer_name TEXT,
    amount REAL
)
""")

cursor.execute("DELETE FROM orders")

sample_data = [
    ("Alice", 2500),
    ("Bob", 1500),
    ("Charlie", 3000),
    ("Alice", 1200),
    ("Bob", 700),
    ("David", 4000)
]

cursor.executemany("INSERT INTO orders (customer_name, amount) VALUES (?, ?)", sample_data)

conn.commit()
conn.close()

print("Database setup complete ")