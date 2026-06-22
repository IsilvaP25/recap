import asyncio
import edge_tts
import re
import os
import argparse
import sys
import subprocess

# Voice selection
VOICE = "es-ES-AlvaroNeural"
RATE = "+25%"

def apply_loudnorm(file_path):
    """Aplica normalización de audio usando ffmpeg loudnorm."""
    temp_path = file_path + ".tmp.mp3"
    cmd = [
        'ffmpeg', '-y', '-i', file_path,
        '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11',
        '-c:a', 'libmp3lame', '-q:a', '2',
        temp_path
    ]
    try:
        # Usamos stdout/stderr=subprocess.DEVNULL para no ensuciar la consola
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            import time
            for attempt in range(5):
                try:
                    os.replace(temp_path, file_path)
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.2)
        else:
            if os.path.exists(temp_path): os.remove(temp_path)
    except Exception as e:
        print(f"  [WARNING] Error en loudnorm para {file_path}: {e}")
        if os.path.exists(temp_path): os.remove(temp_path)

def clean_text_for_speech(text):
    text = re.split(r'\[UPDATE_LORE\]', text, flags=re.IGNORECASE)[0]
    
    # 1. Eliminar charlas/introducciones típicas de la IA (ej. "Aquí está su guión...", "Aquí tienes...")
    conversational_intros = [
        r'(?i)^\s*aquí\s+(?:está|tienes)\s+(?:su|el)?\s*guio?n\s*(?:de\s+narracio?n)?\s*(?:en\s+ingle?s)?\s*:\s*',
        r'(?i)^\s*here\s+is\s+your\s+.*script\s*:\s*',
        r'(?i)^\s*(?:guio?n\s+de\s+narracio?n|narracio?n|resumen|texto)\s*:\s*'
    ]
    for pattern in conversational_intros:
        text = re.sub(pattern, '', text, flags=re.MULTILINE)

    # 2. Eliminar Markdown (negritas, cursivas, títulos, guiones largos al inicio de línea)
    text = text.replace("**", "").replace("*", "").replace("__", "").replace("_", "").replace("#", "")
    text = re.sub(r'(?m)^-\s*', '', text) # Eliminar guiones de diálogo al inicio de línea

    # 3. Eliminar nombres de personajes y etiquetas de diálogo (ej: "NARRADOR:", "PROTAGONISTA (PENSAMIENTO):", "CHARLIE:")
    # Soporta letras castellanas (tildes, eñes) y acotaciones entre paréntesis
    text = re.sub(r'(?im)^\s*[A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s_-]+(?:\s*\([^)]*\))?\s*:\s*', '', text)

    # 4. Eliminar acotaciones técnicas y sonidos descriptivos entre paréntesis o corchetes
    text = re.sub(r'\(.*?\)', '', text, flags=re.DOTALL)
    text = re.sub(r'\[.*?\]', '', text, flags=re.DOTALL)

    # 5. Eliminar símbolos raros
    text = text.replace(">", "").replace("<", "").replace("|", "")
    
    return " ".join(text.split()).strip()

def parse_script(file_path):
    if not os.path.exists(file_path):
        print(f"  [ERROR] No existe el archivo de guion: {file_path}")
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    parts = re.split(r'### PAGE_(\d+)', content)
    parsed_pages = {}
    for i in range(1, len(parts), 2):
        page_num = int(parts[i])
        page_content = parts[i+1]
        cleaned = clean_text_for_speech(page_content)
        if cleaned:
            parsed_pages[page_num] = cleaned
    return parsed_pages

async def generate_single_page_audio(page_num, text, output_folder, semaphore):
    filename = f"PAGE_{page_num:02d}.mp3"
    output_path = os.path.join(output_folder, filename)
    json_path = os.path.join(output_folder, f"PAGE_{page_num:02d}_words.json")
    
    if os.path.exists(output_path) and os.path.exists(json_path):
        return

    async with semaphore:
        try:
            import json
            communicate = edge_tts.Communicate(text, VOICE, rate=RATE, boundary="WordBoundary")
            words_data = []
            with open(output_path, "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        offset_sec = chunk["offset"] / 10000000.0
                        duration_sec = chunk["duration"] / 10000000.0
                        word_text = chunk["text"]
                        words_data.append({
                            "word": word_text,
                            "start": offset_sec,
                            "end": offset_sec + duration_sec
                        })
            
            with open(json_path, "w", encoding="utf-8") as f_json:
                json.dump(words_data, f_json, ensure_ascii=False, indent=2)
                
            # Run ffmpeg normalisation in a separate thread so it doesn't block the async loop
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, apply_loudnorm, output_path)
        except Exception as e:
            sys.stdout.write(f"\nError en Página {page_num}: {e}\n")
            sys.stdout.flush()

async def generate_audio_for_pages(parsed_pages, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    
    # Limit to 5 concurrent API requests to avoid rate limits from edge-tts
    semaphore = asyncio.Semaphore(5)
    
    total_pages = len(parsed_pages)
    completed_pages = 0
    
    def print_progress(completed, total, prefix=''):
        import sys
        longitud = 10
        porcentaje = f"{100 * (completed / float(total)):.1f}%"
        llenado = int(longitud * completed // total)
        barra = '#' * llenado + '-' * (longitud - llenado)
        linea = f"\r\x1b[K{prefix[:20]} |{barra}| {porcentaje}"
        sys.stdout.write(linea)
        sys.stdout.flush()
        
    print_progress(0, total_pages, "Generar Audio")
    
    tasks = []
    for page_num, text in parsed_pages.items():
        async def wrapped_task(p_num, txt, out_fold, sem):
            await generate_single_page_audio(p_num, txt, out_fold, sem)
            nonlocal completed_pages
            completed_pages += 1
            print_progress(completed_pages, total_pages, "Generar Audio")
            
        tasks.append(wrapped_task(page_num, text, output_folder, semaphore))
        
    await asyncio.gather(*tasks)
    print()

async def generate_short_audio(script_path, output_folder, suffix=""):
    import json
    os.makedirs(output_folder, exist_ok=True)
    out_name = f"SHORT_FULL_{suffix}.mp3" if suffix else "SHORT_FULL.mp3"
    json_name = f"SHORT_FULL_{suffix}_words.json" if suffix else "SHORT_FULL_words.json"
    out_path = os.path.join(output_folder, out_name)
    json_path = os.path.join(output_folder, json_name)
    
    if os.path.exists(out_path) and os.path.exists(json_path):
        print(f"Short Audio y word boundaries ({out_name}): Ya existen.")
        return
 
    if not os.path.exists(script_path):
        print(f"Aviso: No se encontró guion short en {script_path}")
        return
 
    print(f"Generando Audio y Word Boundaries para SHORT ({out_name})...")
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    cleaned = clean_text_for_speech(content)
    try:
        communicate = edge_tts.Communicate(cleaned, VOICE, rate=RATE, boundary="WordBoundary")
        words_data = []
        with open(out_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    offset_sec = chunk["offset"] / 10000000.0
                    duration_sec = chunk["duration"] / 10000000.0
                    text = chunk["text"]
                    words_data.append({
                        "word": text,
                        "start": offset_sec,
                        "end": offset_sec + duration_sec
                    })
        
        with open(json_path, "w", encoding="utf-8") as f_json:
            json.dump(words_data, f_json, ensure_ascii=False, indent=2)
            
        apply_loudnorm(out_path)
        print(f"Short Audio Guardado y Normalizado: {out_path}")
        print(f"Word boundaries guardados: {json_path}")
    except Exception as e:
        print(f"Error en Short Audio: {e}")
 
async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manga", required=True)
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--mode", choices=["full", "short", "both"], default="both")
    parser.add_argument("--suffix", default="")
    args = parser.parse_args()
    
    # Ruta absoluta al proyecto
    base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    base_in = os.path.join(base_proj, "outputs", args.manga, "Scripts")
    base_out = os.path.join(base_proj, "outputs", args.manga, "_TEMP", f"Capitulo_{args.chapter}", "audio")
    
    if args.mode in ["full", "both"]:
        # Priorizamos el guion en español si existe
        full_script = os.path.join(base_in, f"Capitulo_{args.chapter}_guion_ESP.txt")
        if not os.path.exists(full_script):
            full_script = os.path.join(base_in, f"Capitulo_{args.chapter}_guion_raw.txt")
            
        data = parse_script(full_script)
        if data:
            await generate_audio_for_pages(data, base_out)
            
    if args.mode in ["short", "both"]:
        script_name = f"Short_guion_ESP_{args.suffix}.txt" if args.suffix else "Short_guion_ESP.txt"
        short_script = os.path.join(base_in, script_name)
        if not os.path.exists(short_script):
            raw_name = f"Short_guion_raw_{args.suffix}.txt" if args.suffix else "Short_guion_raw.txt"
            short_script = os.path.join(base_in, raw_name)
            if not os.path.exists(short_script):
                specific_name = f"Short_guion_{args.suffix}.txt" if args.suffix else "Short_guion.txt"
                short_script = os.path.join(base_in, specific_name)
            
        await generate_short_audio(short_script, base_out, suffix=args.suffix)
 
if __name__ == "__main__":
    asyncio.run(main())
