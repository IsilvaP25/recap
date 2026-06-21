import os
import sqlite3
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "manga_pipeline.db")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

def sync():
    if not os.path.exists(OUTPUTS_DIR):
        print(f"Outputs directory not found at: {OUTPUTS_DIR}")
        return

    print("Connecting to database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ensure table structure
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shorts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manga TEXT UNIQUE,
            content TEXT,
            thumbnail_prompt TEXT,
            status TEXT DEFAULT 'completed',
            is_uploaded INTEGER DEFAULT 0,
            youtube_id TEXT,
            video_created INTEGER DEFAULT 0,
            scheduled_date TEXT
        )
    ''')
    conn.commit()

    mangas = [d for d in os.listdir(OUTPUTS_DIR) if os.path.isdir(os.path.join(OUTPUTS_DIR, d))]
    print(f"Found {len(mangas)} mangas in outputs/ directory.")

    synced_scripts = 0
    checked_mangas = []

    for manga in mangas:
        manga_key = manga.replace(' ', '_')
        scripts_path = os.path.join(OUTPUTS_DIR, manga, "Scripts")
        
        has_script = False
        has_metadata = False
        script_content = None
        
        if os.path.exists(scripts_path):
            raw_script_file = os.path.join(scripts_path, "Short_guion_raw.txt")
            metadata_file = os.path.join(scripts_path, "short_youtube_data.json")
            
            if os.path.exists(raw_script_file):
                has_script = True
                try:
                    with open(raw_script_file, "r", encoding="utf-8") as f:
                        script_content = f.read().strip()
                except Exception as e:
                    print(f"  [ERROR] Reading {raw_script_file}: {e}")
            
            if os.path.exists(metadata_file):
                has_metadata = True

        # If we have a script content, synchronize to DB
        if script_content:
            # Check existing entry
            cursor.execute('SELECT content, thumbnail_prompt, video_created, is_uploaded FROM shorts WHERE manga = ?', (manga_key,))
            row = cursor.fetchone()
            
            # Default values
            default_prompt = f"Epic anime illustration of {manga.replace('_', ' ')} main character, cinematic lighting, high contrast manga style."
            
            # If exists, update content if it was None/empty
            if row:
                db_content, db_prompt, db_video, db_uploaded = row
                update_fields = []
                params = []
                
                if not db_content:
                    update_fields.append("content = ?")
                    params.append(script_content)
                if not db_prompt:
                    update_fields.append("thumbnail_prompt = ?")
                    params.append(default_prompt)
                
                # Check if video file actually exists to mark video_created
                video_file = os.path.join(OUTPUTS_DIR, manga, "VIDEOS", "Short_1.mp4")
                if os.path.exists(video_file) and db_video != 1:
                    update_fields.append("video_created = 1")
                
                if update_fields:
                    query = f"UPDATE shorts SET {', '.join(update_fields)} WHERE manga = ?"
                    params.append(manga_key)
                    cursor.execute(query, tuple(params))
                    synced_scripts += 1
            else:
                # Insert new entry
                video_created = 0
                video_file = os.path.join(OUTPUTS_DIR, manga, "VIDEOS", "Short_1.mp4")
                if os.path.exists(video_file):
                    video_created = 1
                
                cursor.execute('''
                    INSERT INTO shorts (manga, content, thumbnail_prompt, status, video_created)
                    VALUES (?, ?, ?, 'completed', ?)
                ''', (manga_key, script_content, default_prompt, video_created))
                synced_scripts += 1
                
        checked_mangas.append({
            "manga": manga_key,
            "has_script_file": has_script,
            "has_metadata_file": has_metadata,
            "script_length": len(script_content) if script_content else 0
        })

    conn.commit()
    conn.close()
    
    print("\n==================================================")
    print("      --- SYNCHRONIZATION REPORT ---")
    print("==================================================")
    print(f"Scripts synchronized/updated in DB: {synced_scripts}")
    print("\nDetailed Status of Mangas:")
    print(f"{'Manga':<50} | {'Short Script':<12} | {'Short Metadata':<14} | {'DB Status':<12}")
    print("-" * 95)
    
    # Query database again to print the final DB state
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for item in checked_mangas:
        cursor.execute('SELECT content, is_uploaded, video_created FROM shorts WHERE manga = ?', (item["manga"],))
        row = cursor.fetchone()
        db_status = "Not in DB"
        if row:
            db_content, db_uploaded, db_video = row
            if db_uploaded == 2:
                db_status = "Uploaded 2x"
            elif db_uploaded == 1:
                db_status = "Uploaded 1x"
            elif db_video == 1:
                db_status = "Video Created"
            elif db_content:
                db_status = "Has Script"
            else:
                db_status = "Empty Entry"
                
        script_status = "Yes" if item["has_script_file"] else "No"
        meta_status = "Yes" if item["has_metadata_file"] else "No"
        print(f"{item['manga']:<50} | {script_status:<12} | {meta_status:<14} | {db_status:<12}")
        
    conn.close()
    print("==================================================")

if __name__ == "__main__":
    sync()
