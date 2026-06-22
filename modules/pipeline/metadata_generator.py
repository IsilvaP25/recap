import os
import json
import argparse
import sys
import google.generativeai as genai
from dotenv import load_dotenv
try:
    import db_manager
except ImportError:
    from modules.pipeline import db_manager

load_dotenv()
# Asegurar que se puede importar el rotador
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:
    from modules import api_rotator
except ImportError:
    import api_rotator

# Configuración dinámica
genai.configure(api_key=api_rotator.get_any_key())

def clean_manga_title(folder_name):
    # Remove underscores and normalize spaces
    return " ".join(folder_name.replace("__", " ").replace("_", " ").split()).strip()

MODELS_TO_TRY = [
    'gemini-2.5-flash-lite'
]

def get_manga_short_name(manga_name):
    """Obtains or generates a short brand name for the manga (max 25 chars)."""
    import sqlite3
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "database", "manga_pipeline.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS manga_branding (manga TEXT PRIMARY KEY, short_name TEXT)')
    cursor.execute('SELECT short_name FROM manga_branding WHERE manga = ?', (manga_name,))
    row = cursor.fetchone()
    if row:
        conn.close()
        return row[0]
    
    print(f"  [AI] Generando nombre corto de marca para: {manga_name}")
    prompt = f"Provide a short, recognizable, and catchy brand name (max 25 characters) for this manga series: '{manga_name.replace('_', ' ')}'. Output ONLY the name."
    short_name = manga_name.replace('_', ' ')[:25]
    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content(prompt)
        short_name = response.text.strip().replace('"', '').replace("'", "")
    except: pass
    cursor.execute('INSERT INTO manga_branding (manga, short_name) VALUES (?, ?)', (manga_name, short_name))
    conn.commit()
    conn.close()
    return short_name

def generate_metadata(manga_name, start_cap, end_cap, part_num=None):
    print(f"--- Generating Metadata for {manga_name} (Chapters {start_cap}-{end_cap}) ---")
    long_script = db_manager.get_page_script(manga_name, start_cap, 1)
    if not long_script:
        _, long_script = db_manager.get_short_script(manga_name)
        
    manga_title_clean = clean_manga_title(manga_name)
    short_brand_name = get_manga_short_name(manga_name)
    
    prompt = f"""
    You are a Viral Marketing Expert for YouTube Manga Recaps.
    Generate metadata for a video covering chapters {start_cap} to {end_cap} of "{manga_title_clean}".
    
    CONTEXT: {long_script[:2000] if long_script else "No script available"}
    
    REQUIREMENTS:
    1. "hook": Un gancho (hook) viral y pegajoso para el título (máx 45 caracteres, español). Debe usar lenguaje clickbait pero profesional.
    2. "description": Un resumen persuasivo y emocionante del video (español latino neutro).
    3. "thumbnail_prompt": A detailed artistic prompt for AI Image generation (Keep this in English). 
       STYLE: Professional Manga Illustration, high contrast ink, sharp lineart, screentone patterns, cinematic composition.
    
    Output ONLY a JSON object in Spanish (except the thumbnail_prompt).
    """
    
    metadata_raw = None
    for model_name in MODELS_TO_TRY:
        success = False
        # Intentar con todas las claves si falla por cuota
        attempts_without_sleep = 0
        sleep_cycles = 0
        while True:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                json_str = response.text.replace("```json", "").replace("```", "").strip()
                if "{" in json_str:
                    json_str = json_str[json_str.find("{"):json_str.rfind("}")+1]
                metadata_raw = json.loads(json_str)
                success = True
                break
            except Exception as e:
                err = str(e).lower()
                if "429" in err or "quota" in err or "limit" in err:
                    failed_key = api_rotator.get_current_key()
                    api_rotator.report_failed_key(failed_key)
                    attempts_without_sleep += 1
                    if attempts_without_sleep >= len(api_rotator.get_all_keys()):
                        sleep_cycles += 1
                        if sleep_cycles > 2:
                            print(f"\n[ROTATOR] Límite de espera excedido ({sleep_cycles} ciclos) para {model_name}. Probando siguiente modelo...")
                            break
                        print("\n[ROTATOR] Se han agotado todas las API keys en el pool (cuota excedida). Esperando 60 segundos antes de reintentar...")
                        import time
                        time.sleep(60)
                        attempts_without_sleep = 0
                    new_key = api_rotator.get_next_key()
                    genai.configure(api_key=new_key)
                    print(f"  [ROTATOR] Reintentando generación con nueva clave...")
                    continue
                else:
                    break
        if success: break

    if not metadata_raw: return None
    
    hook = metadata_raw.get("hook", "Epic Battle")
    
    # Si no se pasa el numero de parte, lo calculamos con la nueva base 7
    if part_num is None:
        part_num = int(float(start_cap)) // 7 + 1
        
    part_info = f"#P{part_num}"
    cap_info = f"(Caps {start_cap}-{end_cap})"
    final_title = f"{hook} {part_info} {cap_info} | {short_brand_name}"
    
    if len(final_title) > 100:
        over = len(final_title) - 100
        hook = hook[:-over-3] + "..."
        final_title = f"{hook} {part_info} {cap_info} | {short_brand_name}"

    final_metadata = {
        "clickbait_title": final_title,
        "description": metadata_raw.get("description", "") + f"\n\nSerie: {manga_title_clean}\nCapítulos: {start_cap} al {end_cap}",
        "thumbnail_prompt": metadata_raw.get("thumbnail_prompt", "Professional Manga Art"),
        "manga_folder": manga_name,
        "chapter_range": f"{start_cap}-{end_cap}"
    }
    
    base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    output_dir = os.path.join(base_proj, "outputs", manga_name, "Scripts")
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"Capitulo_{start_cap}_metadata.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final_metadata, f, indent=4, ensure_ascii=False)
    print(f"  [OK] Metadata saved (Title: {len(final_title)} chars): {out_path}")
    return out_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manga", required=True)
    parser.add_argument("--start", required=False)
    parser.add_argument("--end", required=False)
    parser.add_argument("--short", action="store_true", help="Generate metadata for Short")
    parser.add_argument("--part", type=int, default=None)
    args = parser.parse_args()
    
    db_manager.init_db()
    
    if args.short:
        print(f"--- Generating SHORT Metadata for {args.manga} ---")
        short_script, _ = db_manager.get_short_script(args.manga)
        if not short_script:
            print("  [ERROR] No short script found in DB.")
            sys.exit(1)
            
        manga_title_clean = clean_manga_title(args.manga)
        short_brand_name = get_manga_short_name(args.manga)
        
        prompt = f"""
        You are a Viral Marketing Expert for YouTube Shorts.
        Generate metadata for a SHORT video of the manga "{manga_title_clean}".
        
        CONTEXT: {short_script[:1000]}
        
        REQUIREMENTS:
        1. "hook": A viral and catchy title (max 50 characters, Spanish). Use #Shorts.
           CRITICAL TITLE RULES:
           - MUST prefer starting the title with a question mark (e.g., "¿...?").
           - MUST prefer including extreme intrigue words (in uppercase) such as: "MÁS DÉBIL", "OP", "REGRESA", "VIVE", "TRAICIONADO", "ERROR FATAL", "VENGANZA SANGRIENTA", "MURIÓ 100 VECES".
           - MUST include at least one relevant emoticon/emoji (e.g., 😱, 🤯, 💔, 😈, 😭).
        2. "description": A very brief and punchy description with hashtags like #manga #recap #shorts.
        
        Output ONLY a JSON object in Spanish.
        """
        
        metadata_raw = None
        for model_name in MODELS_TO_TRY:
            success = False
            attempts_without_sleep = 0
            sleep_cycles = 0
            while True:
                try:
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(prompt)
                    json_str = response.text.replace("```json", "").replace("```", "").strip()
                    if "{" in json_str:
                        json_str = json_str[json_str.find("{"):json_str.rfind("}")+1]
                    metadata_raw = json.loads(json_str)
                    success = True
                    break
                except Exception as e:
                    err = str(e).lower()
                    if "429" in err or "quota" in err or "limit" in err:
                        failed_key = api_rotator.get_current_key()
                        api_rotator.report_failed_key(failed_key)
                        attempts_without_sleep += 1
                        if attempts_without_sleep >= len(api_rotator.get_all_keys()):
                            sleep_cycles += 1
                            if sleep_cycles > 2:
                                print(f"\n[ROTATOR] Límite de espera excedido ({sleep_cycles} ciclos) para {model_name}. Probando siguiente modelo...")
                                break
                            print("\n[ROTATOR] Se han agotado todas las API keys en el pool (cuota excedida). Esperando 60 segundos antes de reintentar...")
                            import time
                            time.sleep(60)
                            attempts_without_sleep = 0
                        new_key = api_rotator.get_next_key()
                        genai.configure(api_key=new_key)
                        print(f"  [ROTATOR] Reintentando generación con nueva clave...")
                        continue
                    else: break
            if success: break

        if not metadata_raw:
            print("  [ERROR] Could not generate short metadata.")
            sys.exit(1)
            
        final_metadata = {
            "clickbait_title": metadata_raw.get("hook", f"{manga_title_clean} Recap #Shorts"),
            "description": metadata_raw.get("description", "") + f"\n\n#manga #recap #shorts #anime",
            "manga_folder": args.manga
        }
        
        base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        output_dir = os.path.join(base_proj, "outputs", args.manga, "Scripts")
        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, "short_youtube_data.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(final_metadata, f, indent=4, ensure_ascii=False)
        print(f"  [OK] Short Metadata saved: {out_path}")
    else:
        if args.start is None or args.end is None:
            print("  [ERROR] --start and --end are required for full video metadata.")
            sys.exit(1)
        res = generate_metadata(args.manga, args.start, args.end, args.part)
        if not res:
            print("  [ERROR] Could not generate full video metadata.")
            sys.exit(1)
