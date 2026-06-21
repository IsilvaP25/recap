import sqlite3
import os
import shutil

# Paths
base_dir = r"c:\Users\ignacio\Desktop\Nueva carpeta (2)\end to end\Proyecto manga recap"
pipeline_db = os.path.join(base_dir, "database", "manga_pipeline.db")
output_dir = os.path.join(base_dir, "outputs", "Single_Dad_In_Another_World")

print("--- Clearing database and output files for Single_Dad_In_Another_World ---")

# 1. Clear database entries
try:
    conn = sqlite3.connect(pipeline_db)
    cursor = conn.cursor()
    
    # Delete from shorts
    cursor.execute("DELETE FROM shorts WHERE manga = 'Single_Dad_In_Another_World'")
    print(f"Deleted from shorts: {cursor.rowcount} rows")
    
    # Delete from scripts
    cursor.execute("DELETE FROM scripts WHERE manga = 'Single_Dad_In_Another_World'")
    print(f"Deleted from scripts: {cursor.rowcount} rows")
    
    # Delete from pipeline_parts
    cursor.execute("DELETE FROM pipeline_parts WHERE manga = 'Single_Dad_In_Another_World'")
    print(f"Deleted from pipeline_parts: {cursor.rowcount} rows")
    
    # Delete from story_history
    cursor.execute("DELETE FROM story_history WHERE manga = 'Single_Dad_In_Another_World'")
    print(f"Deleted from story_history: {cursor.rowcount} rows")
    
    conn.commit()
    conn.close()
except Exception as e:
    print(f"Error clearing database: {e}")

# 2. Clear physical files
if os.path.exists(output_dir):
    try:
        shutil.rmtree(output_dir)
        print(f"Removed output directory: {output_dir}")
    except Exception as e:
        print(f"Error removing output directory: {e}")
else:
    print("Output directory does not exist or was already removed.")

print("Clear completed successfully.")
