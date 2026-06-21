import sqlite3
import os

base_proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(base_proj, "database", "manga_recap.db")

print("Resetting database upload status for long videos...")
try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Reset pipeline_parts
    cur.execute("UPDATE pipeline_parts SET is_uploaded = 0, youtube_id = NULL")
    parts_reset = cur.rowcount
    print(f"Reset {parts_reset} rows in pipeline_parts.")
    
    # Reset last_main_upload in global_config
    cur.execute("UPDATE global_config SET value = NULL WHERE key = 'last_main_upload'")
    config_reset = cur.rowcount
    print(f"Reset last_main_upload in global_config (affected {config_reset} rows).")
    
    conn.commit()
    conn.close()
    print("Database reset completed successfully.")
except Exception as e:
    print(f"Error during database reset: {e}")
