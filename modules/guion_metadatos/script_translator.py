import os
import argparse
import re
from deep_translator import GoogleTranslator
import sys
# Añadir la carpeta raíz al path para importar módulos correctamente
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from modules import db_manager
except ImportError:
    from modules import db_manager

def is_spanish(text):
    if not text:
        return False
    # Check if text has Spanish stop words
    words = set(re.findall(r'\b\w+\b', text.lower()))
    spanish_indicators = {'el', 'la', 'los', 'las', 'un', 'una', 'y', 'que', 'en', 'de', 'con', 'es', 'del', 'al', 'para', 'por', 'se'}
    english_indicators = {'the', 'and', 'of', 'to', 'a', 'in', 'is', 'that', 'it', 'he', 'was', 'for', 'on', 'are', 'with', 'as', 'his'}
    
    sp_count = len(words.intersection(spanish_indicators))
    en_count = len(words.intersection(english_indicators))
    return sp_count > en_count or (sp_count >= 2 and en_count == 0)

def translate_chapter(manga_name, chapter_num):
    print(f"--- Translating Chapter {chapter_num} of {manga_name} ---")
    translator = GoogleTranslator(source='en', target='es')
    
    # 1. Translate page scripts in DB
    # We'll get all pages for this chapter
    import sqlite3
    conn = sqlite3.connect(db_manager.DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT page_num, content FROM scripts WHERE manga = ? AND chapter = ?', (manga_name, chapter_num))
    rows = cursor.fetchall()
    
    if not rows:
        print("  No scripts found in DB to translate.")
    else:
        total_pages = len(rows)
        completed = 0
        def print_progress(completed, total, prefix=''):
            import sys
            longitud = 10
            porcentaje = f"{100 * (completed / float(total)):.1f}%"
            llenado = int(longitud * completed // total)
            barra = '#' * llenado + '-' * (longitud - llenado)
            linea = f"\r\x1b[K{prefix[:20]} |{barra}| {porcentaje}"
            sys.stdout.write(linea)
            sys.stdout.flush()

        print_progress(0, total_pages, "Traducir Guion")
        for p_num, content in rows:
            if is_spanish(content):
                completed += 1
                print_progress(completed, total_pages, "Traducir Guion")
                continue
            
            try:
                spanish_text = translator.translate(content)
                db_manager.save_page_script(manga_name, chapter_num, p_num, spanish_text)
            except Exception as e:
                sys.stdout.write(f"\n    Error translating page {p_num}: {e}\n")
                sys.stdout.flush()
            completed += 1
            print_progress(completed, total_pages, "Traducir Guion")
        print()

    # 2. Translate Short if exists
    short_content, thumb_prompt = db_manager.get_short_script(manga_name)
    if short_content:
        if is_spanish(short_content):
            print("  SHORT script is already in Spanish. Skipping translation.")
        else:
            print("  Translating SHORT script...")
            try:
                spanish_short = translator.translate(short_content)
                # Normalizar etiquetas traducidas (ej. [Página: 1] -> [PAGE:1])
                spanish_short = re.sub(r'\[(?:PAGE|PÁGINA|PAGINA)\s*[:\-\s]*(\d+)\]', r'[PAGE:\1]', spanish_short, flags=re.IGNORECASE)
                db_manager.save_short_script(manga_name, spanish_short, thumb_prompt)
            except Exception as e:
                print(f"    Error translating short: {e}")
    
    conn.close()

    # 3. Re-generate the .txt files with Spanish content
    base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    base_out = os.path.join(base_proj, "outputs", manga_name, "Scripts")
    os.makedirs(base_out, exist_ok=True)
    
    full_script_path = os.path.join(base_out, f"Capitulo_{chapter_num}_guion_ESP.txt")
    short_script_path = os.path.join(base_out, "Short_guion_ESP.txt")
    
    # Reconstruct full script
    cons = []
    # Get total pages from DB
    import sqlite3
    conn = sqlite3.connect(db_manager.DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT MAX(page_num) FROM scripts WHERE manga = ? AND chapter = ?', (manga_name, chapter_num))
    total_pages = cursor.fetchone()[0] or 0
    conn.close()

    for i in range(total_pages):
        page_num = i+1
        script = db_manager.get_page_script(manga_name, chapter_num, page_num)
        if script:
            cons.append(f"### PAGE_{page_num:02d}\n\n{script}")
            
    if cons:
        with open(full_script_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(cons))
        print(f"  Spanish Full Script saved: {full_script_path}")

    # Reconstruct short script from DB
    short_content, _ = db_manager.get_short_script(manga_name)
    if short_content:
        with open(short_script_path, "w", encoding="utf-8") as f:
            f.write(short_content)
        print(f"  Spanish Short Script saved: {short_script_path}")

    # 4. Translate Metadata JSON if exists
    meta_paths = [
        os.path.join(base_out, f"Capitulo_{chapter_num}_metadata.json"),
    ]
    
    import json
    for meta_path in meta_paths:
        if os.path.exists(meta_path):
            print(f"  Checking Metadata: {meta_path}...")
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                modified = False
                if "clickbait_title" in data and not is_spanish(data["clickbait_title"]):
                    translated_title = translator.translate(data["clickbait_title"])
                    if len(translated_title) > 100:
                        translated_title = translated_title[:97] + "..."
                    data["clickbait_title"] = translated_title
                    modified = True
                if "description" in data and not is_spanish(data["description"]):
                    data["description"] = translator.translate(data["description"])
                    modified = True
                
                if "thumbnail_prompt" in data and not is_spanish(data["thumbnail_prompt"]):
                    data["thumbnail_prompt"] = translator.translate(data["thumbnail_prompt"])
                    modified = True
                
                if modified:
                    with open(meta_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                    print("    [OK] Metadata translated to Spanish.")
                else:
                    print("    [OK] Metadata is already in Spanish or skipped translation.")
            except Exception as e:
                print(f"    [!] Error translating metadata: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manga", required=True)
    parser.add_argument("--chapter", required=True)
    args = parser.parse_args()
    
    db_manager.init_db()
    translate_chapter(args.manga, args.chapter)
