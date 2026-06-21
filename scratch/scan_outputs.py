import os
import sqlite3
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "manga_pipeline.db")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

def scan():
    if not os.path.exists(OUTPUTS_DIR):
        print(f"Outputs directory not found at: {OUTPUTS_DIR}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    mangas = [d for d in os.listdir(OUTPUTS_DIR) if os.path.isdir(os.path.join(OUTPUTS_DIR, d))]
    
    report = []
    
    for manga in mangas:
        manga_key = manga.replace(' ', '_')
        manga_path = os.path.join(OUTPUTS_DIR, manga)
        scripts_path = os.path.join(manga_path, "Scripts")
        videos_path = os.path.join(manga_path, "VIDEOS")
        
        # Files on disk
        short_raw = False
        short_esp = False
        short_meta = False
        short_video = False
        long_scripts = []
        long_metas = []
        
        if os.path.exists(scripts_path):
            for file in os.listdir(scripts_path):
                file_lower = file.lower()
                file_path = os.path.join(scripts_path, file)
                if file == "Short_guion_raw.txt":
                    short_raw = True
                elif file == "Short_guion_ESP.txt":
                    short_esp = True
                elif file == "short_youtube_data.json":
                    short_meta = True
                elif "guion_raw" in file_lower:
                    long_scripts.append(file)
                elif "youtube_data" in file_lower and not file.startswith("short"):
                    long_metas.append(file)
                    
        if os.path.exists(videos_path):
            for file in os.listdir(videos_path):
                if file == "Short_1.mp4":
                    short_video = True
        
        # Database shorts table info
        db_has_short = False
        db_short_content = None
        db_short_uploaded = 0
        db_short_video_created = 0
        db_short_yt_id = None
        
        try:
            cursor.execute('SELECT content, is_uploaded, video_created, youtube_id FROM shorts WHERE manga = ?', (manga_key,))
            row = cursor.fetchone()
            if row:
                db_has_short = True
                db_short_content = row[0]
                db_short_uploaded = row[1]
                db_short_video_created = row[2]
                db_short_yt_id = row[3]
        except sqlite3.OperationalError:
            pass
            
        # Database scripts table (long scripts count)
        db_long_pages = 0
        try:
            cursor.execute('SELECT COUNT(*) FROM scripts WHERE manga = ?', (manga_key,))
            db_long_pages = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            pass
            
        # Database pipeline_parts table (long videos parts)
        db_parts = []
        try:
            cursor.execute('SELECT part_number, start_chapter, end_chapter, status, is_uploaded, youtube_id FROM pipeline_parts WHERE manga = ?', (manga_key,))
            for r in cursor.fetchall():
                db_parts.append({
                    "part": r[0],
                    "start": r[1],
                    "end": r[2],
                    "status": r[3],
                    "is_uploaded": r[4],
                    "youtube_id": r[5]
                })
        except sqlite3.OperationalError:
            pass

        report.append({
            "manga": manga,
            "short_raw": short_raw,
            "short_esp": short_esp,
            "short_meta": short_meta,
            "short_video": short_video,
            "long_scripts": long_scripts,
            "long_metas": long_metas,
            "db_has_short": db_has_short,
            "db_short_has_content": bool(db_short_content),
            "db_short_uploaded": db_short_uploaded,
            "db_short_video_created": db_short_video_created,
            "db_short_yt_id": db_short_yt_id,
            "db_long_pages": db_long_pages,
            "db_parts": db_parts
        })
        
    conn.close()
    
    # Save the report as JSON
    with open(os.path.join(BASE_DIR, "scratch", "scan_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4, ensure_ascii=False)
        
    print(f"Scanned {len(report)} folders. Saved JSON report.")
    
    # Write a human readable summary to console
    print("\nSUMMARY:")
    for r in report:
        has_s = "YES" if r["short_raw"] else "NO"
        has_m = "YES" if r["short_meta"] else "NO"
        db_s = "YES" if r["db_short_has_content"] else "NO"
        print(f"- {r['manga']}: Short Script: Disk={has_s}, DB={db_s} | Short Meta: Disk={has_m} | Long Scripts: {len(r['long_scripts'])} files | Parts in DB: {len(r['db_parts'])}")

if __name__ == "__main__":
    scan()
