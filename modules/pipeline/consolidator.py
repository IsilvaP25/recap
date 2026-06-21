import os
import shutil
import json
import argparse
import sys
import subprocess
import re
from modules.api_config import obtener_capitulos_por_parte

def format_cap(num):
    try:
        val = float(num)
        return str(int(val)) if val == int(val) else str(val)
    except (ValueError, TypeError):
        return str(num)

def get_chapters_in_range(manga_name, start_cap, end_cap):
    base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pdf_dir = os.path.join(base_proj, "pdf_storage", manga_name)
    chapters = set()
    
    if os.path.exists(pdf_dir):
        def extract_num(fn):
            m = re.search(r'(\d+\.\d+|\d+)', fn)
            return float(m.group(1)) if m else 0.0
        for f in os.listdir(pdf_dir):
            if f.endswith(".pdf"):
                num = extract_num(f)
                if num > 0:
                    chapters.add(num)
                    
    temp_dir = os.path.join(base_proj, "outputs", manga_name, "_TEMP")
    if os.path.exists(temp_dir):
        for d in os.listdir(temp_dir):
            if d.startswith("Capitulo_"):
                try:
                    num_str = d.replace("Capitulo_", "")
                    chapters.add(float(num_str))
                except ValueError:
                    pass
                    
    videos_dir = os.path.join(base_proj, "outputs", manga_name, "VIDEOS")
    if os.path.exists(videos_dir):
        for f in os.listdir(videos_dir):
            if f.startswith("Capitulo_") and f.endswith(".mp4"):
                try:
                    num_str = f.replace("Capitulo_", "").replace(".mp4", "")
                    chapters.add(float(num_str))
                except ValueError:
                    pass
                    
    start_val = float(start_cap)
    end_val = float(end_cap)
    filtered_chapters = [c for c in chapters if start_val <= c <= end_val]
    return sorted(filtered_chapters)

def calculate_chapter_timestamps(manga_name, chapters):
    base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    def get_video_duration(video_path):
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            return float(res.stdout)
        except:
            return 0.0

    current_time = 0.0
    timestamps = []
    
    for cap in chapters:
        cap_str = format_cap(cap)
        seconds = int(current_time)
        hrs = seconds // 3600
        mins = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hrs > 0:
            timestamp_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"
        else:
            timestamp_str = f"{mins:02d}:{secs:02d}"
            
        timestamps.append(f"{timestamp_str} - Capitulo {cap_str}")
        
        cap_temp_dir = os.path.join(base_proj, "outputs", manga_name, "_TEMP", f"Capitulo_{cap_str}", "video", "temp_segments")
        chapter_duration = 0.0
        
        if os.path.exists(cap_temp_dir):
            segs = sorted([os.path.join(cap_temp_dir, f) for f in os.listdir(cap_temp_dir) if f.endswith(".mp4")])
            for s in segs:
                chapter_duration += get_video_duration(s)
        else:
            indiv_video = os.path.join(base_proj, "outputs", manga_name, "VIDEOS", f"Capitulo_{cap_str}.mp4")
            if os.path.exists(indiv_video):
                chapter_duration = get_video_duration(indiv_video)
                print(f"  [INFO] Usando duración del video del capítulo {cap_str}: {chapter_duration}s")
            else:
                # NEW FALLBACK: Estimate using database word count
                print(f"  [INFO] Archivos no encontrados. Estimando duración usando DB para cap {cap_str}...")
                try:
                    import sqlite3
                    db_path = os.path.join(base_proj, "database", "manga_recap.db")
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute('SELECT content FROM scripts WHERE manga = ? AND chapter = ? ORDER BY page_num', (manga_name, float(cap)))
                    rows = cursor.fetchall()
                    conn.close()
                    if rows:
                        for r in rows:
                            text = r[0]
                            if text:
                                w_count = len(text.split())
                                chapter_duration += (w_count / 3.47) + 0.1
                            else:
                                chapter_duration += 5.1
                    else:
                        chapter_duration = 150.0
                except Exception as ex:
                    print(f"  [AVISO] Error al estimar: {ex}")
                    chapter_duration = 150.0
                print(f"  [INFO] Duración estimada para capítulo {cap_str}: {chapter_duration:.2f}s")
                
        current_time += chapter_duration
            
    return "\n".join(timestamps)

def update_youtube_metadata_description(metadata_path, timestamps_text, tags_text):
    if not os.path.exists(metadata_path):
        return
        
    with open(metadata_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    original_description = data.get("description", "")
    lines = original_description.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        if re.match(r'^\d{2}:\d{2}(:\d{2})?\s*-\s*Capitulo', stripped):
            continue
        if stripped.startswith("Tags: resumen de manhwa"):
            continue
        cleaned_lines.append(line)
        
    cleaned_desc = "\n".join(cleaned_lines).strip()
    new_description = cleaned_desc + "\n\n" + timestamps_text.strip() + "\n\n" + tags_text.strip()
    data["description"] = new_description
    
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def consolidate_manga_content(manga_name, start_cap, end_cap, part_num=None):
    """
    Organizes final video, thumbnail, and metadata into a clean 
    READY_TO_PUBLISH folder within the manga output directory.
    """
    base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    manga_dir = os.path.join(base_proj, "outputs", manga_name)
    
    if not os.path.exists(manga_dir):
        print(f"[ERROR] Manga directory not found: {manga_dir}")
        return False

    # Si no se pasa el numero de parte, lo calculamos con la nueva base configurada
    if part_num is None:
        part_num = int(float(start_cap)) // obtener_capitulos_por_parte() + 1

    # Define target launch folder
    publish_base = os.path.join(manga_dir, "FINAL_PUBLICATION")
    launch_folder = os.path.join(publish_base, f"Recap_Parte_{part_num}_Caps_{start_cap}_al_{end_cap}")
    os.makedirs(launch_folder, exist_ok=True)

    print(f"\n--- Consolidating Final Content: {manga_name} ---")

    # 1. Final Video (MegaRecap)
    video_filename = f"MegaRecap_{start_cap}_al_{end_cap}.mp4"
    video_src = os.path.join(manga_dir, "VIDEOS", video_filename)
    
    if os.path.exists(video_src):
        shutil.copy2(video_src, os.path.join(launch_folder, "video_final.mp4"))
        print(f"  [OK] Video consolidated: video_final.mp4")
    else:
        print(f"  [ERROR] MegaRecap video not found in: {video_src}")
        sys.exit(1)

    # 2. Thumbnail
    thumb_filename = f"MegaRecap_{start_cap}_al_{end_cap}.png"
    thumb_src = os.path.join(manga_dir, "MINIATURAS", thumb_filename)
    
    if os.path.exists(thumb_src):
        shutil.copy2(thumb_src, os.path.join(launch_folder, "thumbnail.png"))
        print(f"  [OK] Thumbnail consolidated: thumbnail.png")
    else:
        print(f"  [ERROR] Thumbnail not found in: {thumb_src}")
        sys.exit(1)

    # 3. Metadata
    meta_filename = f"Capitulo_{start_cap}_metadata.json"
    meta_src = os.path.join(manga_dir, "Scripts", meta_filename)
    dest_meta = os.path.join(launch_folder, "youtube_data.json")
    
    # Calculate timestamps and tags
    chapters = get_chapters_in_range(manga_name, start_cap, end_cap)
    print(f"  [INFO] Capítulos en rango para timestamps: {chapters}")
    timestamps_text = calculate_chapter_timestamps(manga_name, chapters)
    tags_text = "Tags: resumen de manhwa, resumen manga, resumen de manga, manhwa, mangas, manhua, resumen completo, resumen, resumen de anime, resumenes de manhwas, resumenes de manhua, resumenes de animes, resumen de manhwa completo, resumen de manhua completo, resumen de manhwa nuevo,resumen de manhwa op, manhwas resumenes, manhwa resumen"

    if os.path.exists(meta_src):
        # Copy to final destination
        shutil.copy2(meta_src, dest_meta)
        
        # Update destination metadata file
        update_youtube_metadata_description(dest_meta, timestamps_text, tags_text)
        
        # Also update source metadata file so they stay in sync
        update_youtube_metadata_description(meta_src, timestamps_text, tags_text)
        
        print(f"  [OK] Metadata consolidated and updated: youtube_data.json")
    elif os.path.exists(dest_meta):
        # Update destination metadata file in-place
        update_youtube_metadata_description(dest_meta, timestamps_text, tags_text)
        print(f"  [OK] Destination metadata updated in-place: youtube_data.json")
    else:
        print(f"  [ERROR] Metadata not found in source ({meta_src}) or destination ({dest_meta})")
        sys.exit(1)

    # 4. Handle Short (Only if Chapter 1)
    if float(start_cap) == 1.0:
        short_launch = os.path.join(publish_base, "Short_Gancho_Inicial")
        os.makedirs(short_launch, exist_ok=True)
        
        short_video_src = os.path.join(manga_dir, "VIDEOS", "Short_1.mp4")
        if os.path.exists(short_video_src):
            shutil.copy2(short_video_src, os.path.join(short_launch, "short_video.mp4"))
            print(f"  [OK] Short video consolidated: {short_launch}")
        
        short_meta_src = os.path.join(manga_dir, "Scripts", "Capitulo_1_short_guion_ESP.txt")
        if os.path.exists(short_meta_src):
             shutil.copy2(short_meta_src, os.path.join(short_launch, "short_script.txt"))

    print(f"\n[SUCCESS] Content ready for upload in: {launch_folder}")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manga", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--part", type=int, default=None)
    args = parser.parse_args()
    
    consolidate_manga_content(args.manga, args.start, args.end, args.part)
