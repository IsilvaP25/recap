import sqlite3
import os

base_proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(base_proj, "database", "manga_recap.db")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Get table names
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print("Tables:", tables)

# Get schema of each table
for table in tables:
    table_name = table[0]
    print(f"\nSchema of {table_name}:")
    cur.execute(f"PRAGMA table_info({table_name})")
    info = cur.fetchall()
    for col in info:
        print(f"  {col[1]} ({col[2]})")

# If there is an uploads table or similar, print its content
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='uploads'")
if cur.fetchone():
    print("\nUploads table rows:")
    cur.execute("SELECT * FROM uploads LIMIT 10")
    for row in cur.fetchall():
        print(row)

conn.close()
