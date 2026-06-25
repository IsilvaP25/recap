import os
import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image
import time
import argparse
import sys
import fitz  # PyMuPDF
import io
import re

# Añadir la carpeta raíz al path para importar módulos correctamente
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from modules import db_manager
except ImportError:
    # Fallback para cuando se ejecuta desde la raíz del proyecto
    from modules import db_manager

from google.generativeai.types import HarmCategory, HarmBlockThreshold

base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from modules import api_rotator
except ImportError:
    import api_rotator

load_dotenv(os.path.join(base_dir, '.env'))
# Inicializar con una clave del pool
genai.configure(api_key=api_rotator.get_any_key())

def print_progress(completed, total, prefix=''):
    longitud = 10
    porcentaje = f"{100 * (completed / float(total)):.1f}%"
    llenado = int(longitud * completed // total)
    barra = '#' * llenado + '-' * (longitud - llenado)
    linea = f"\r\x1b[K  [{prefix}] |{barra}| {porcentaje}"
    sys.stdout.write(linea)
    sys.stdout.flush()

SAFETY_SETTINGS = [
    { "category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_NONE },
    { "category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_NONE },
    { "category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_NONE },
    { "category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_NONE },
]

MODELS_TO_TRY = [
    'gemini-2.5-flash-lite'
]

GENERATION_CONFIG = {
    "temperature": 0.7
}

DEFAULT_BATCH_SIZE = 5

def get_lore_context():
    try:
        with open("data/lore_bible.json", "r", encoding="utf-8") as f: return f.read()
    except Exception: return "{}"

def clean_garbage_text(text):
    # Eliminar frases comunes que la IA cuela por error
    garbage_patterns = [
        r'^(?:Esta es la\s+)?portada\s*(?:oficial)?[:\-\s]*',
        r'^(?:En esta\s+)?p[áa]gina[:\-\s]*\d*',
        r'^(?:Imagen de\s+)?portada[:\-\s]*',
        r'^Transcripci[oó]n[:\-\s]*',
        r'^Guion[:\-\s]*'
    ]
    for pattern in garbage_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE).strip()
    return text

def get_system_instruction(language="es", rag_context=""):
    lore = get_lore_context()
    if language == "es":
        lang_instruction = "Escribe la narración en ESPAÑOL LATINO NEUTRO. El estilo debe ser altamente entretenido y dinámico, ideal para un narrador de resúmenes de manga en YouTube."
    else:
        lang_instruction = "Write the narration in ENGLISH. The style should be highly engaging and dynamic, ideal for a YouTube manga recap narrator."
        
    rag_part = f"\nMemoria histórica de capítulos anteriores:\n{rag_context}\n" if rag_context else ""
    
    return f"""
Senior Scriptwriter. Lore (Spanish): {lore}.
{rag_part}
{lang_instruction}
ABSOLUTE RULE: Output ONLY the story narration text and page markers.
ZERO TOLERANCE: Do NOT include 'Cover', 'Page', 'Image', 'Flashback', or any visual/technical description.
STRICT SAFETY: If any page contains sensitive, prohibited, or NSFW content, simply provide a neutral, safe summary of the plot events without describing the prohibited parts. DO NOT GENERATE SENSITIVE CONTENT.
START IMMEDIATELY with the first marker.
Example of the ONLY acceptable output:
### PAGE_01
(The story begins here...)
### PAGE_02
(The story continues...)
"""

def flexible_parse(text):
    # Try multiple patterns but normalize results
    found = {}
    
    # Pattern 1: ### PAGE_XX
    parts = re.split(r'### PAGE_(\d+)', text, flags=re.IGNORECASE)
    if len(parts) > 1:
        for k in range(1, len(parts), 2): found[int(parts[k])] = parts[k+1].strip()
        return found
        
    # Pattern 2: PAGE XX or Pagina XX
    parts = re.split(r'(?:PAGE|PÁGINA|PAGINA)\s*[:\-\s]*(\d+)', text, flags=re.IGNORECASE)
    if len(parts) > 1:
        for k in range(1, len(parts), 2): found[int(parts[k])] = parts[k+1].strip()
        return found

    # Pattern 3: \d+ . 
    parts = re.split(r'(?m)^(\d+)\s*[:\.]+', text)
    if len(parts) > 1:
        for k in range(1, len(parts), 2): found[int(parts[k])] = parts[k+1].strip()
        return found
        
    return found

def generate_script_from_pdf(pdf_path, manga_name, chapter_num, output_file, batch_size=DEFAULT_BATCH_SIZE, limit_pages=None, language="es"):
    db_manager.init_db()
    try: doc = fitz.open(pdf_path)
    except Exception as e: return False
        
    total_pages = len(doc); 
    if limit_pages: total_pages = min(total_pages, limit_pages)

    # Initial progress
    pending = [i+1 for i in range(total_pages) if not db_manager.get_page_script(manga_name, chapter_num, i+1)]
    completed_pages = total_pages - len(pending)
    print_progress(completed_pages, total_pages, prefix="Guion Recap")

    # Obtener memoria de capítulos anteriores usando RAG (solo para videos largos)
    rag_context = ""
    try:
        from modules.gemini import vector_manager
        consulta = f"historia, personajes principales y eventos importantes del manga {manga_name}"
        rag_context = vector_manager.obtener_contexto_historico(manga_name, chapter_num, consulta, top_k=3)
    except Exception:
        pass

    active_models = list(MODELS_TO_TRY)
    while True:
        pending = [i+1 for i in range(total_pages) if not db_manager.get_page_script(manga_name, chapter_num, i+1)]
        if not pending:
            print_progress(total_pages, total_pages, prefix="Guion Recap")
            print()
            break
            
        actual_batch = batch_size if batch_size > 0 else len(pending)
        batch_nums = pending[:actual_batch]
        
        imgs = []
        for p_num in batch_nums:
            page = doc.load_page(p_num - 1)
            pix = page.get_pixmap(matrix=fitz.Matrix(1.0,1.0))
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            
            if img.height > 16000:
                scale = 16000 / img.height
                img = img.resize((int(img.width * scale), 16000), Image.LANCZOS)
            
            imgs.append(img)
            
        batch_success = False
        to_rem = []
        for model_name in active_models:
            attempts_without_sleep = 0
            sleep_cycles = 0
            total_active_keys = max(1, len(api_rotator.get_all_keys()))
            while True:
                try:
                    model = genai.GenerativeModel(
                        model_name, 
                        system_instruction=get_system_instruction(language, rag_context=rag_context),
                        safety_settings=SAFETY_SETTINGS,
                        generation_config=GENERATION_CONFIG
                    )
                    if language == "es":
                        prompt = (f"Crea una narración de historia ORIGINAL, APTA PARA TODO PÚBLICO y emocionante para estas {len(batch_nums)} páginas en ESPAÑOL LATINO NEUTRO para un resumen de manga. "
                                 f"NO describas ningún contenido sensible, prohibido o NSFW. Concéntrate únicamente en el progreso de la trama y las interacciones seguras de los personajes. "
                                 f"Comienza directamente con ### PAGE_{batch_nums[0]}. Sin transcripciones con derechos de autor.")
                    else:
                        prompt = (f"Create an ORIGINAL, FAMILY-FRIENDLY story summary/narration for these {len(batch_nums)} pages in English for accessibility purposes. "
                                 f"DO NOT describe any sensitive, prohibited, or NSFW content. Focus only on plot progression and safe character interactions. "
                                 f"Start directly with ### PAGE_{batch_nums[0]}. No copyrighted transcriptions.")
                    response = model.generate_content([prompt] + imgs, request_options={"timeout": 60})
                    
                    try:
                        resp_text = response.text
                    except ValueError as ve:
                        if "candidate" in str(ve).lower() or "block_reason" in str(ve).lower():
                            for p_num in batch_nums:
                                db_manager.save_page_script(manga_name, chapter_num, p_num, "(Escena bloqueada por filtros de seguridad de IA)")
                            batch_success = True
                            break
                        else:
                            raise ve
                            
                    if not resp_text: raise Exception("Vacío.")
                    
                    found = flexible_parse(resp_text)
                    missing = [p for p in batch_nums if p not in found]
                    if missing: raise Exception(f"Faltan pág: {missing}")
                    
                    for p_num in batch_nums: 
                        english_text = clean_garbage_text(found[p_num])
                        db_manager.save_page_script(manga_name, chapter_num, p_num, english_text)
                    
                    pending_now = [i+1 for i in range(total_pages) if not db_manager.get_page_script(manga_name, chapter_num, i+1)]
                    completed_pages = total_pages - len(pending_now)
                    print_progress(completed_pages, total_pages, prefix="Guion Recap")
                    batch_success = True; break
                except Exception as e:
                    err = str(e).lower()
                    if "429" in err or "quota" in err or "limit" in err:
                        failed_key = api_rotator.get_current_key()
                        api_rotator.report_failed_key(failed_key)
                        mask = failed_key[-4:] if failed_key else "unknown"
                        print(f"\n  [ROTATOR] La clave ...{mask} ha fallado o alcanzado límite. Buscando siguiente...")
                        attempts_without_sleep += 1
                        if attempts_without_sleep >= total_active_keys:
                            sleep_cycles += 1
                            if sleep_cycles > 2:
                                to_rem.append(model_name)
                                break
                            print("  [ROTATOR] Se han agotado todas las API keys en el pool (cuota excedida). Esperando 60 segundos antes de reintentar...")
                            time.sleep(60)
                            attempts_without_sleep = 0
                        new_key = api_rotator.get_next_key()
                        print("  [ROTATOR] Reintentando generación con nueva clave...")
                        genai.configure(api_key=new_key)
                        continue
                    elif any(x in err for x in ["deadline", "timeout", "connection", "unavailable", "socket", "502", "503", "504"]):
                        print(f"\n  [CONEXIÓN] La llamada se ha colgado o agotado el tiempo de espera. Reintentando con la misma clave en 10 segundos...")
                        time.sleep(10)
                        continue
                    else:
                        print(f"\n  [ERROR] Error inesperado en generación de guión: {type(e).__name__}: {e}")
                        break
            
            if batch_success: break
 
        for m in to_rem: 
            if m in active_models: active_models.remove(m)
        if not batch_success:
            if not active_models:
                print("\n[CRITICAL] Todos los modelos de IA disponibles han fallado o agotado su cuota.")
                print("El proceso se detiene aquí para evitar bucles infinitos.")
            doc.close(); return False
        time.sleep(2)
    
    doc.close()
    # RECONSTRUCTION IN IDENTICAL FORMAT
    cons = []
    for i in range(total_pages):
        page_num = i+1
        script = db_manager.get_page_script(manga_name, chapter_num, page_num)
        if script:
            # If script already has header (old entries), clean it
            clean_script = re.sub(r'### PAGE_\d+', '', script).strip()
            cons.append(f"### PAGE_{page_num:02d}\n\n{clean_script}")
            
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f: f.write("\n\n".join(cons))
    print(f"Guion IDENTICO y verificado guardado: {output_file}")

    # Generar memoria histórica y guardarla en SQLite y base vectorial ChromaDB
    try:
        generate_historical_summary(manga_name, chapter_num)
    except Exception as ge:
        print(f"  [HISTORIA] [AVISO] Error al actualizar memoria histórica: {ge}")

    return True

def generate_short_summary(pdf_path, manga_name, output_file, force=False, language="es"):
    # Verificar si ya existe en DB y en disco
    existing_script, existing_prompt = db_manager.get_short_script(manga_name)
    
    file_exists = os.path.exists(output_file)
    
    if existing_script and file_exists and not force:
        print(f"  [SKIP] Short ya existe (DB + Disco).")
        return True

    # Si existe en DB pero falta el archivo físico (y no es force), intentamos recuperarlo de la DB
    if existing_script and not file_exists and not force:
        print(f"  [RECOVERY] Recuperando guión desde la base de datos...")
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f: f.write(existing_script)
        return True

    # Si existe en disco pero falta en la DB (y no es force), lo importamos a la DB
    if not existing_script and file_exists and not force:
        print(f"  [RECOVERY] Guión encontrado en disco pero ausente en DB. Importando a la DB...")
        with open(output_file, "r", encoding="utf-8") as f:
            disk_script = f.read().strip()
        db_manager.save_short_script(manga_name, disk_script, f"Epic anime illustration of {manga_name.replace('_', ' ')} main character, cinematic lighting, high contrast manga style.")
        return True

    # Si llegamos aquí, es porque falta algo o se pidió force
    # 1. Intentar obtener guiones de página de la DB para generar por texto
    import sqlite3
    conn = sqlite3.connect(db_manager.DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT page_num, content FROM scripts WHERE manga = ? AND chapter = 1 ORDER BY page_num', (manga_name.replace(' ', '_'),))
        db_rows = cursor.fetchall()
    except Exception:
        db_rows = []
    conn.close()

    if language == "es":
        system_short = (
            f"Narrador Experto. Lore: {get_lore_context()}. "
            f"REGLA ABSOLUTA: Genera ÚNICAMENTE el guión de narración en ESPAÑOL LATINO NEUTRO con marcadores de página, seguido de 'THUMBNAIL_PROMPT' y la sugerencia de miniatura en inglés. "
            f"TOLERANCIA CERO: NO incluyas textos de introducción (como 'Aquí está tu guión'), charlas o títulos como 'Guión de Narración:'. "
            f"COMIENZA INMEDIATAMENTE con el primer marcador (ej. [PAGE:1]). "
            f"El guión del resumen debe cubrir TODO el capítulo de principio a fin. "
            f"Mantén el resumen extremadamente conciso, ajustado y de menos de 170 palabras en español (garantizando una duración de lectura de menos de 56 segundos a un ritmo rápido). "
            f"Debes etiquetar y hacer referencia a entre 10 y 15 páginas clave únicas en total usando etiquetas [PAGE:XX] (ej. [PAGE:1] al narrar los eventos de la página 1, [PAGE:5] para la página 5, etc.). "
            f"Selecciona solo las páginas más importantes (Gancho, Conflicto Inicial, Clímax y Desenlace con suspenso) y evita paneles visualmente repetitivos o transiciones menores. Asegúrate de cubrir el clímax y el final cerca de las últimas páginas. "
            f"LUEGO, al final, proporciona 'THUMBNAIL_PROMPT' seguido de una sugerencia detallada en INGLÉS para generar una miniatura de alto impacto en YouTube (estilo manga épico, iluminación cinematográfica, enfoque en el personaje principal)."
        )
    else:
        system_short = (
            f"Expert Narrator. Lore: {get_lore_context()}. "
            f"ABSOLUTE RULE: Output ONLY the narration script with page markers, followed by 'THUMBNAIL_PROMPT' and the thumbnail prompt. "
            f"ZERO TOLERANCE: Do NOT include introductory text (like 'Here is your script'), conversational chatter, or titles like 'Narration Script:'. "
            f"START IMMEDIATELY with the first marker (e.g., [PAGE:1]). "
            f"The summary script must cover the ENTIRE chapter from start to finish. "
            f"Keep the summary extremely concise, tight, and under 140 words (guaranteeing a speaking duration of under 56 seconds/175 words when translated to Spanish and read at a fast pace). "
            f"You must tag and reference between 10 and 15 unique key pages in total using [PAGE:XX] tags (e.g. [PAGE:1] when narrating page 1 events, [PAGE:5] for page 5, etc.). "
            f"Select only the most important pages (Hook, Rising Action, Climax, and Cliffhanger Ending) and avoid visually repetitive panels or minor transitions. Ensure you cover the climax and ending near the final pages."
            f"THEN, at the end, provide a 'THUMBNAIL_PROMPT' for a high-impact YouTube thumbnail (epic, cinematic, focus on main character)."
        )

    if len(db_rows) > 0:
        print_progress(0, 1, prefix="Guion Short")
        full_text = "\n".join([f"PAGE {r[0]}: {r[1]}" for r in db_rows])
        for model_name in MODELS_TO_TRY:
            success = False
            attempts_without_sleep = 0
            sleep_cycles = 0
            total_active_keys = max(1, len(api_rotator.get_all_keys()))
            while True:
                try:
                    model = genai.GenerativeModel(
                        model_name, 
                        system_instruction=system_short,
                        safety_settings=SAFETY_SETTINGS,
                        generation_config=GENERATION_CONFIG
                    )
                    if language == "es":
                        prompt = (
                            f"Genera un guión de resumen en español altamente enganchador y de ritmo rápido de todo el capítulo (máximo 170 palabras) usando etiquetas [PAGE:XX]. "
                            f"Debes seleccionar y etiquetar entre 10 y 15 páginas clave únicas de las etiquetas PAGE para mantener el ritmo dinámico pero legible. "
                            f"El resumen debe cubrir toda la trama de principio a fin, haciendo referencia a los números de página correctos. Comienza de inmediato con [PAGE:1]. Luego proporciona 'THUMBNAIL_PROMPT' al final.\n\n"
                            f"Descripciones detalladas de las páginas:\n{full_text}"
                        )
                    else:
                        prompt = (
                            f"Generate a highly engaging, fast-paced English summary script of the entire chapter (maximum 140 words) using [PAGE:XX] tags. "
                            f"You must select and tag between 10 and 15 unique key pages from the PAGE labels to keep the pacing dynamic yet readable. "
                            f"The summary must cover the entire plot from start to finish, referencing correct page numbers. Start immediately with [PAGE:1]. Then provide 'THUMBNAIL_PROMPT' at the end.\n\n"
                            f"Detailed Page Descriptions:\n{full_text}"
                        )
                    response = model.generate_content(prompt, request_options={"timeout": 60})
                    full_resp = response.text
                    
                    if "THUMBNAIL_PROMPT" in full_resp:
                        script_part = full_resp.split("THUMBNAIL_PROMPT")[0].strip()
                        thumb_part = full_resp.split("THUMBNAIL_PROMPT")[-1].replace(":", "").strip()
                    else:
                        script_part = full_resp.strip()
                        thumb_part = "Manga epic scene, cinematic lighting, main character focus"
        
                    script_part = re.sub(r'(?i)^\s*(?:Here is the script|Here is your script|Here\'s your script|Narration Script|Guion de narracion|Guion de narración|Guion|Guión)\s*.*?:?\s*', '', script_part, flags=re.MULTILINE)
                    script_part = re.sub(r'\*\*+Narration Script:\*\*+', '', script_part, flags=re.IGNORECASE)
                    script_part = re.sub(r'\*\*+Guión de Narración:\*\*+', '', script_part, flags=re.IGNORECASE)
                    script_part = script_part.strip()
        
                    db_manager.save_short_script(manga_name, script_part, thumb_part)
                    os.makedirs(os.path.dirname(output_file), exist_ok=True)
                    with open(output_file, "w", encoding="utf-8") as f: f.write(script_part)
                    print_progress(1, 1, prefix="Guion Short")
                    print()
                    return True
                except Exception as e:
                    err = str(e).lower()
                    if "429" in err or "quota" in err or "limit" in err:
                        failed_key = api_rotator.get_current_key()
                        api_rotator.report_failed_key(failed_key)
                        mask = failed_key[-4:] if failed_key else "unknown"
                        print(f"\n  [ROTATOR] La clave ...{mask} ha fallado o alcanzado límite. Buscando siguiente...")
                        attempts_without_sleep += 1
                        if attempts_without_sleep >= total_active_keys:
                            sleep_cycles += 1
                            if sleep_cycles > 2:
                                break
                            print("  [ROTATOR] Se han agotado todas las API keys en el pool (cuota excedida). Esperando 60 segundos antes de reintentar...")
                            time.sleep(60)
                            attempts_without_sleep = 0
                        new_key = api_rotator.get_next_key()
                        print("  [ROTATOR] Reintentando Short con nueva clave...")
                        genai.configure(api_key=new_key)
                        continue
                    elif any(x in err for x in ["deadline", "timeout", "connection", "unavailable", "socket", "502", "503", "504"]):
                        print(f"\n  [CONEXIÓN] La llamada se ha colgado o agotado el tiempo de espera. Reintentando con la misma clave en 10 segundos...")
                        time.sleep(10)
                        continue
                    else:
                        print(f"\n  [ERROR] Error inesperado en generación de guión short (texto): {type(e).__name__}: {e}")
                        break
        return False

    doc = fitz.open(pdf_path)
    indices = list(range(len(doc)))
    imgs = []
    for idx in indices:
        page = doc.load_page(idx)
        zoom = 600 / page.rect.width if page.rect.width > 600 else 1.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        if img.height > 16000:
            scale = 16000 / img.height
            img = img.resize((int(img.width * scale), 16000), Image.LANCZOS)
        imgs.append(img)

    print_progress(0, 1, prefix="Guion Short")
    image_success = False
    for model_name in MODELS_TO_TRY:
        success = False
        attempts_without_sleep = 0
        sleep_cycles = 0
        total_active_keys = max(1, len(api_rotator.get_all_keys()))
        while True:
            try:
                model = genai.GenerativeModel(
                    model_name, 
                    system_instruction=system_short,
                    safety_settings=SAFETY_SETTINGS,
                    generation_config=GENERATION_CONFIG
                )
                if language == "es":
                    prompt_parts = [
                        "Genera un guión de resumen en español altamente enganchador y de ritmo rápido de todo el capítulo (máximo 170 palabras, adecuado para un Short de YouTube de 60 segundos) usando etiquetas [PAGE:XX]. "
                        "Debes seleccionar y etiquetar entre 10 y 15 páginas clave únicas de las etiquetas PAGE para mantener el ritmo dinámico pero legible. "
                        "El resumen debe cubrir toda la trama de principio a fin, haciendo referencia a los números de página correctos. Comienza de inmediato con [PAGE:1]. Luego proporciona 'THUMBNAIL_PROMPT' al final en inglés."
                    ]
                else:
                    prompt_parts = [
                        "Generate a highly engaging, fast-paced English summary script of the entire chapter (maximum 140 words, suitable for a 60-70 second YouTube Short with a 10% safety margin) using [PAGE:XX] tags. "
                        "You must select and tag between 10 and 15 unique key pages from the PAGE labels to keep the pacing dynamic yet readable. "
                        "The summary must cover the entire plot from start to finish, referencing correct page numbers. Start immediately with [PAGE:1]. Then provide 'THUMBNAIL_PROMPT' at the end."
                    ]
                for idx, img in zip(indices, imgs):
                    prompt_parts.append(f"PAGE {idx+1}:")
                    prompt_parts.append(img)
                    
                response = model.generate_content(prompt_parts, request_options={"timeout": 60})
                full_resp = response.text
                
                if "THUMBNAIL_PROMPT" in full_resp:
                    script_part = full_resp.split("THUMBNAIL_PROMPT")[0].strip()
                    thumb_part = full_resp.split("THUMBNAIL_PROMPT")[-1].replace(":", "").strip()
                else:
                    script_part = full_resp.strip()
                    thumb_part = "Manga epic scene, cinematic lighting, main character focus"
    
                script_part = re.sub(r'(?i)^\s*(?:Here is the script|Here is your script|Here\'s your script|Narration Script|Guion de narracion|Guion de narración|Guion|Guión)\s*.*?:?\s*', '', script_part, flags=re.MULTILINE)
                script_part = re.sub(r'\*\*+Narration Script:\*\*+', '', script_part, flags=re.IGNORECASE)
                script_part = re.sub(r'\*\*+Guión de Narración:\*\*+', '', script_part, flags=re.IGNORECASE)
                script_part = script_part.strip()
    
                db_manager.save_short_script(manga_name, script_part, thumb_part)
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                with open(output_file, "w", encoding="utf-8") as f: f.write(script_part)
                print_progress(1, 1, prefix="Guion Short")
                print()
                success = True
                image_success = True
                break
            except Exception as e: 
                err = str(e).lower()
                if "429" in err or "quota" in err or "limit" in err:
                    failed_key = api_rotator.get_current_key()
                    api_rotator.report_failed_key(failed_key)
                    mask = failed_key[-4:] if failed_key else "unknown"
                    print(f"\n  [ROTATOR] La clave ...{mask} ha fallado o alcanzado límite. Buscando siguiente...")
                    attempts_without_sleep += 1
                    if attempts_without_sleep >= total_active_keys:
                        sleep_cycles += 1
                        if sleep_cycles > 2:
                            break
                        print("  [ROTATOR] Se han agotado todas las API keys en el pool (cuota excedida). Esperando 60 segundos antes de reintentar...")
                        time.sleep(60)
                        attempts_without_sleep = 0
                    new_key = api_rotator.get_next_key()
                    print("  [ROTATOR] Reintentando Short con nueva clave...")
                    genai.configure(api_key=new_key)
                    continue
                elif any(x in err for x in ["deadline", "timeout", "connection", "unavailable", "socket", "502", "503", "504"]):
                    print(f"\n  [CONEXIÓN] La llamada se ha colgado o agotado el tiempo de espera. Reintentando con la misma clave en 10 segundos...")
                    time.sleep(10)
                    continue
                else:
                    print(f"\n  [ERROR] Error inesperado en generación de guión short (imagen): {type(e).__name__}: {e}")
                    break
        if success:
            doc.close()
            return True
            
    doc.close()

    if not image_success:
        base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        temp_full_script = os.path.join(base_proj, "outputs", manga_name, "Scripts", f"Capitulo_1_guion_raw.txt")
        ok = generate_script_from_pdf(pdf_path, manga_name, 1, temp_full_script)
        if not ok:
            return False
            
        conn = sqlite3.connect(db_manager.DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT page_num, content FROM scripts WHERE manga = ? AND chapter = 1 ORDER BY page_num', (manga_name.replace(' ', '_'),))
        db_rows = cursor.fetchall()
        conn.close()
        
        if len(db_rows) > 0:
            print_progress(0, 1, prefix="Guion Short")
            full_text = "\n".join([f"PAGE {r[0]}: {r[1]}" for r in db_rows])
            for model_name in MODELS_TO_TRY:
                success = False
                attempts_without_sleep = 0
                sleep_cycles = 0
                total_active_keys = max(1, len(api_rotator.get_all_keys()))
                while True:
                    try:
                        model = genai.GenerativeModel(
                            model_name, 
                            system_instruction=system_short,
                            safety_settings=SAFETY_SETTINGS,
                            generation_config=GENERATION_CONFIG
                        )
                        if language == "es":
                            prompt = (
                                f"Genera un guión de resumen en español altamente enganchador y de ritmo rápido de todo el capítulo (máximo 170 palabras) usando etiquetas [PAGE:XX]. "
                                f"Debes seleccionar y etiquetar entre 10 y 15 páginas clave únicas de las etiquetas PAGE para mantener el ritmo dinámico pero legible. "
                                f"El resumen debe cubrir toda la trama de principio a fin, haciendo referencia a los números de página correctos. Comienza de inmediato con [PAGE:1]. Luego proporciona 'THUMBNAIL_PROMPT' al final.\n\n"
                                f"Descripciones detalladas de las páginas:\n{full_text}"
                            )
                        else:
                            prompt = (
                                f"Generate a highly engaging, fast-paced English summary script of the entire chapter (maximum 140 words) using [PAGE:XX] tags. "
                                f"You must select and tag between 10 and 15 unique key pages from the PAGE labels to keep the pacing dynamic yet readable. "
                                f"The summary must cover the entire plot from start to finish, referencing correct page numbers. Start immediately with [PAGE:1]. Then provide 'THUMBNAIL_PROMPT' at the end.\n\n"
                                f"Detailed Page Descriptions:\n{full_text}"
                            )
                        response = model.generate_content(prompt, request_options={"timeout": 60})
                        full_resp = response.text
                        
                        if "THUMBNAIL_PROMPT" in full_resp:
                            script_part = full_resp.split("THUMBNAIL_PROMPT")[0].strip()
                            thumb_part = full_resp.split("THUMBNAIL_PROMPT")[-1].replace(":", "").strip()
                        else:
                            script_part = full_resp.strip()
                            thumb_part = "Manga epic scene, cinematic lighting, main character focus"
            
                        script_part = re.sub(r'(?i)^\s*(?:Here is the script|Here is your script|Here\'s your script|Narration Script|Guion de narracion|Guion de narración|Guion|Guión)\s*.*?:?\s*', '', script_part, flags=re.MULTILINE)
                        script_part = re.sub(r'\*\*+Narration Script:\*\*+', '', script_part, flags=re.IGNORECASE)
                        script_part = re.sub(r'\*\*+Guión de Narración:\*\*+', '', script_part, flags=re.IGNORECASE)
                        script_part = script_part.strip()
            
                        db_manager.save_short_script(manga_name, script_part, thumb_part)
                        os.makedirs(os.path.dirname(output_file), exist_ok=True)
                        with open(output_file, "w", encoding="utf-8") as f: f.write(script_part)
                        print_progress(1, 1, prefix="Guion Short")
                        print()
                        return True
                    except Exception as e:
                        err = str(e).lower()
                        if "429" in err or "quota" in err or "limit" in err:
                            failed_key = api_rotator.get_current_key()
                            api_rotator.report_failed_key(failed_key)
                            mask = failed_key[-4:] if failed_key else "unknown"
                            print(f"\n  [ROTATOR] La clave ...{mask} ha fallado o alcanzado límite. Buscando siguiente...")
                            attempts_without_sleep += 1
                            if attempts_without_sleep >= total_active_keys:
                                sleep_cycles += 1
                                if sleep_cycles > 2:
                                    break
                                print("  [ROTATOR] Se han agotado todas las API keys en el pool (cuota excedida). Esperando 60 segundos antes de reintentar...")
                                time.sleep(60)
                                attempts_without_sleep = 0
                            new_key = api_rotator.get_next_key()
                            print("  [ROTATOR] Reintentando Short con nueva clave...")
                            genai.configure(api_key=new_key)
                            continue
                        elif any(x in err for x in ["deadline", "timeout", "connection", "unavailable", "socket", "502", "503", "504"]):
                            print(f"\n  [CONEXIÓN] La llamada se ha colgado o agotado el tiempo de espera. Reintentando con la misma clave en 10 segundos...")
                            time.sleep(10)
                            continue
                        else:
                            print(f"\n  [ERROR] Error inesperado en generación de guión short (fallback): {type(e).__name__}: {e}")
                            break
                            
    return False

def generate_historical_summary(manga_name, chapter_num):
    print(f"--- Generating Historical Memory for Cap {chapter_num} ---")
    
    import sqlite3
    conn = sqlite3.connect(db_manager.DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT content FROM scripts WHERE manga = ? AND chapter = ? ORDER BY page_num', (manga_name, chapter_num))
    rows = cursor.fetchall()
    full_text = "\n".join([r[0] for r in rows])
    conn.close()
    
    if not full_text: 
        print("  [ERROR] No text found for history.")
        return
    
    current_history, _, _ = db_manager.get_story_history(manga_name)
    
    model = genai.GenerativeModel("gemini-2.5-flash-lite", generation_config=GENERATION_CONFIG)
    prompt = f"""
    Current Story History: {current_history if current_history else "No history yet."}
    
    New Chapter ({chapter_num}) Script:
    {full_text[:5000]}...
    
    Update the story history. Provide a 5-line executive summary of the story events SO FAR in Spanish.
    Focus only on the plot facts and character evolution. Output ONLY the summary.
    """
    
    try:
        response = model.generate_content(prompt)
        db_manager.save_story_history(manga_name, chapter_num, response.text)
        print(f"  [OK] History updated for chapter {chapter_num}")
        
        # Guardar también en la base de datos vectorial ChromaDB para RAG (solo para videos largos)
        try:
            from modules.gemini import vector_manager
            vector_manager.guardar_resumen_capitulo(manga_name, chapter_num, response.text)
        except Exception as ve:
            print(f"  [VECTORS] [ERROR] No se pudo indexar el resumen del capítulo en ChromaDB: {ve}")
            
    except Exception as e:
        print(f"  [WARNING] Could not update history: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manga", required=True)
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--mode", default="both")
    parser.add_argument("--batch_size", type=int, default=5)
    parser.add_argument("--force", action="store_true", help="Force regeneration of files and DB entries")
    parser.add_argument("--language", default="es", choices=["es", "en"], help="Target language for script generation")
    args = parser.parse_args()
    
    # Ruta absoluta al proyecto
    base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    base_out = os.path.join(base_proj, "outputs", args.manga, "Scripts")
    os.makedirs(base_out, exist_ok=True)
    s = True
    if args.mode in ["full", "both"]: 
        full_path = os.path.join(base_out, f"Capitulo_{args.chapter}_guion_raw.txt")
        s = generate_script_from_pdf(args.pdf, args.manga, args.chapter, full_path, batch_size=args.batch_size, language=args.language)
    
    s_short = True
    if s and args.mode in ["short", "both"]: 
        short_path = os.path.join(base_out, "Short_guion_raw.txt")
        s_short = generate_short_summary(args.pdf, args.manga, short_path, force=args.force, language=args.language)
    
    if not s or not s_short: sys.exit(1)
