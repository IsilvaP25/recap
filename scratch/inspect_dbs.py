import sqlite3
import os

db1 = 'database/manga_pipeline.db'
db2 = 'database/manga_recap.db'

def inspect(db_path):
    print(f"\n=== INSPECTING: {db_path} ===")
    if not os.path.exists(db_path):
        print("File does not exist")
        return
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cursor.fetchall()]
    print("Tables:", tables)
    for table in tables:
        print(f"\nTable: {table}")
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [c[1] for c in cursor.fetchall()]
        print("Columns:", columns)
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"Row count: {count}")
        if count > 0:
            cursor.execute(f"SELECT * FROM {table} LIMIT 5")
            print("First 5 rows:")
            for r in cursor.fetchall():
                print(r)
    conn.close()

inspect(db1)
inspect(db2)
