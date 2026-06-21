import sqlite3
import os

def main():
    db_paths = [
        "database/manga_pipeline.db",
        "database/manga_recap.db"
    ]
    for db_path in db_paths:
        if not os.path.exists(db_path):
            print(f"{db_path} does not exist.")
            continue
        print(f"\n--- Database: {db_path} ---")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"Tables: {tables}")
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  Table '{table}' has {count} rows.")
                if table == 'shorts':
                    cursor.execute("SELECT manga, content, thumbnail_prompt FROM shorts")
                    rows = cursor.fetchall()
                    for r in rows:
                        print(f"    Short: manga={r[0]}, content_len={len(r[1]) if r[1] else 0}, prompt={r[2]}")
            conn.close()
        except Exception as e:
            print(f"Error reading {db_path}: {e}")

if __name__ == "__main__":
    main()
