import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "database", "manga_recap.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT manga, is_uploaded, youtube_id, scheduled_date 
        FROM shorts 
        WHERE scheduled_date IS NOT NULL
        ORDER BY scheduled_date DESC
        LIMIT 20
    """)
    rows = cursor.fetchall()
    print("Latest 20 scheduled shorts:")
    for r in rows:
        print(r)
        
    conn.close()

if __name__ == "__main__":
    main()
