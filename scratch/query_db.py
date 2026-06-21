import sqlite3
import os

base_proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(base_proj, "database", "manga_recap.db")
print("DB Path:", db_path)

conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT * FROM pipeline_parts WHERE manga LIKE ?", ("%Single_Aristocrat%",))
rows = cur.fetchall()
for row in rows:
    print(row)
conn.close()
