import sqlite3
import sys

db_path = 'database/manga_recap.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("PRAGMA table_info(guiones)")
    columns = cursor.fetchall()
    print("Schema of 'guiones' table:")
    for col in columns:
        print(col)
        
    cursor.execute("SELECT COUNT(*) FROM guiones")
    count = cursor.fetchone()[0]
    print(f"\nTotal rows in 'guiones' table: {count}")
    
    if count > 0:
        cursor.execute("SELECT manga_id, capitulos, json_metadata IS NOT NULL FROM guiones LIMIT 5")
        print("\nSample rows (manga_id, capitulos, has_json_metadata):")
        for r in cursor.fetchall():
            print(r)
except Exception as e:
    print("Error:", e)
finally:
    conn.close()
