import sqlite3
import os

db_path = 'database/manga_recap.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT titulo, tipo FROM mangas")
    rows = cursor.fetchall()
    for row in rows:
        print(f"Manga: {row[0]} | Tipo: {row[1]}")
    conn.close()
else:
    print("Database not found.")
