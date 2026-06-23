import os
import re
import json
import requests
import argparse
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip('/')
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL_IA", "llama3.2")

def rewrite_page_text(page_text, page_num, model_name=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL):
    """
    Envía únicamente el texto de una página a Ollama para su reescritura en aislamiento.
    """
    url = f"{base_url}/api/generate"
    
    system_instruction = (
        "Eres un editor y redactor de guiones experto para YouTube Shorts. "
        "Tu tarea consiste en reescribir y parafrasear un breve fragmento de narración de manga en ESPAÑOL LATINO NEUTRO. "
        "REGLA CRÍTICA: Explica el mismo suceso de forma dinámica pero utilizando palabras y expresiones distintas. "
        "TOLERANCIA CERO: Devuelve EXCLUSIVAMENTE la narración reescrita. No agregues la etiqueta de página, no agregues explicaciones, introducciones ni textos de cierre."
    )
    
    payload = {
        "model": model_name,
        "prompt": f"Reescribe la siguiente narración:\n{page_text}",
        "system": system_instruction,
        "options": {
            "temperature": 0.5
        },
        "stream": False
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        res_text = response.json().get("response", "").strip()
        
        # Limpiar posibles prefacios del modelo
        res_text = re.sub(r'(?i)^\s*(?:Here is the rewritten text|Reescritura|Parafraseo|Narración|Texto reescrito)\s*:\s*', '', res_text)
        return res_text.strip()
    except Exception as e:
        print(f"  [ERROR] Error en Ollama al procesar Página {page_num}: {e}")
        # En caso de error, devolvemos el texto original como fallback
        return page_text

def rewrite_script_by_pages(script_content, model_name=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL):
    """
    Parsea el guion por marcas de [PAGE:X], reescribe cada sección de manera aislada,
    y reensambla el guion resultante manteniendo las marcas originales.
    """
    # Encontrar todas las marcas [PAGE:X] o [PAGE:XX]
    matches = list(re.finditer(r'\[PAGE:(\d+)\]', script_content))
    if not matches:
        print("  [WARNING] No se encontraron marcadores [PAGE:X] en el guion para reescribir por páginas.")
        # Fallback: Procesar el guion entero si no tiene marcas
        return rewrite_page_text(script_content, "completo", model_name, base_url)
        
    rewritten_sections = []
    for idx, match in enumerate(matches):
        page_num = match.group(1)
        start_idx = match.end()
        end_idx = matches[idx + 1].start() if idx + 1 < len(matches) else len(script_content)
        page_text = script_content[start_idx:end_idx].strip()
        
        print(f"  [Ollama] Reescribiendo [PAGE:{page_num}] en aislamiento...")
        rewritten_text = rewrite_page_text(page_text, page_num, model_name, base_url)
        rewritten_sections.append(f"[PAGE:{page_num}] {rewritten_text}")
        
    return "\n\n".join(rewritten_sections)

def generate_metadata(script_content, model_name=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, original_hashtags="", manga_name=""):
    """
    Genera título y descripción de YouTube Shorts en formato JSON usando Ollama.
    Aplica una configuración fuertemente orientada a clickbait y añade los hashtags especificados.
    """
    url = f"{base_url}/api/generate"
    
    manga_label = manga_name.replace("_", " ") if manga_name else ""
    
    system_instruction = (
        "Eres un experto en marketing de YouTube Shorts y redacción publicitaria en ESPAÑOL LATINO. "
        "Tu única tarea es generar un objeto JSON válido con las claves 'clickbait_title' y 'description'. "
        "No agregues texto introductorio, explicaciones, ni bloques de código de markdown (como ```json). "
        "Produce un JSON limpio y puro."
    )
    
    prompt = (
        f"Basándote en el siguiente guión de un Short de YouTube, genera metadatos llamativos y clickbait en español.\n\n"
        f"GUIÓN:\n{script_content}\n\n"
        f"REGLAS CRÍTICAS PARA EL TÍTULO ('clickbait_title'):\n"
        f"1. Debe ser corto (máximo 55 caracteres).\n"
        f"2. Debe ser extremadamente intrigante y emocionante y NO debe incluir el nombre del manga en el título.\n"
        f"3. Debe empezar con el signo de interrogación español '¿' y terminar con '?' (ejemplo: ¿Es el fin de todo?). NUNCA comiences con '?¿' ni dupliques los signos de interrogación.\n"
        f"4. Debe incluir obligatoriamente al menos una de estas palabras de intriga extrema en MAYÚSCULAS: MÁS DÉBIL, OP, REGRESA, VIVE, TRAICIONADO, ERROR FATAL, VENGANZA SANGRIENTA, MURIÓ 100 VECES.\n"
        f"5. Debe incluir obligatoriamente al menos un emoji o emoticón llamativo (ej. 😱, 🤯, 💔, 😈, 😭) al final o dentro del título.\n"
        f"6. Revisa la ortografía y gramática en español. Evita palabras inventadas o traducciones literales incorrectas.\n\n"
        f"REGLAS CRÍTICAS PARA LA DESCRIPCIÓN ('description'):\n"
        f"1. Escribe un resumen muy corto y dinámico (de 1 o 2 líneas) de la trama del Short.\n"
        f"2. Debe ser intrigante para que el usuario quiera ver el video.\n"
        f"3. NUNCA la dejes vacía o en blanco.\n"
        f"4. NO agregues hashtags por tu cuenta.\n\n"
        f"FORMATO DE SALIDA REQUERIDO:\n"
        f"Un objeto JSON con esta estructura exacta:\n"
        f"{{\n"
        f"  \"clickbait_title\": \"título aquí\",\n"
        f"  \"description\": \"resumen de la trama aquí\"\n"
        f"}}"
    )
    
    payload = {
        "model": model_name,
        "prompt": prompt,
        "system": system_instruction,
        "format": "json",
        "options": {
            "temperature": 0.3
        },
        "stream": False
    }
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        res_json_str = response.json().get("response", "").strip()
        
        meta = json.loads(res_json_str)
        
        # Programmatic guardrails for clickbait title
        title = meta.get("clickbait_title", "").strip()
        
        # 1. Clean double starting question marks (e.g. ?¿ or ??)
        title = re.sub(r'^[?¿\s]*\?¿', '¿', title)
        title = re.sub(r'^\?+', '¿', title)
        
        # Ensure it starts with ¿
        if not title.startswith('¿'):
            title = '¿' + title
            
        # Ensure it has a closing ?
        if '?' not in title:
            # Try to place it before emojis
            has_placed = False
            for idx, c in enumerate(title):
                if ord(c) > 0x1000:  # Simple emoji/special character detection
                    title = title[:idx].strip() + '?' + title[idx:]
                    has_placed = True
                    break
            if not has_placed:
                title = title + '?'
                
        # 2. Ensure at least one emoji exists in the title, if not append a default
        has_emoji = False
        for char in title:
            codepoint = ord(char)
            if (0x1F300 <= codepoint <= 0x1F9FF) or (0x2600 <= codepoint <= 0x27BF) or (0x1F600 <= codepoint <= 0x1F64F):
                has_emoji = True
                break
        if not has_emoji:
            title = title.strip() + " 😱"
            
        meta["clickbait_title"] = title
        
        # Limpiar cualquier hashtag que el modelo haya podido poner de todos modos
        desc = meta.get("description", "").strip()
        desc_clean = re.sub(r'#\w+', '', desc).strip()
        
        # Si la descripción quedó vacía tras la limpieza o la generación, poner un fallback
        if not desc_clean:
            desc_clean = f"¿Listo para conocer la historia de {manga_label}? No te pierdas este emocionante resumen."
            
        if not original_hashtags:
            # Generar hashtags por defecto usando el nombre del manga
            manga_tag = f"#{manga_name.replace('_', '').replace(' ', '')}" if manga_name else ""
            original_hashtags = f"{manga_tag} #manga #recap #shorts #anime".strip()
            # Limpiar posibles espacios duplicados
            original_hashtags = re.sub(r'\s+', ' ', original_hashtags)
            
        meta["description"] = f"{desc_clean}\n\n{original_hashtags}"
            
        return meta
    except Exception as e:
        print(f"  [ERROR] Error al generar metadatos con Ollama: {e}")
        # Retornar una estructura básica de fallback
        default_desc = "Una historia fascinante que no te puedes perder."
        if original_hashtags:
            default_desc = f"{default_desc}\n\n{original_hashtags}"
        return {
            "clickbait_title": f"Recap de {manga_label} #Shorts" if manga_label else "¡Manga Recap increíble! #Shorts",
            "description": default_desc
        }

if __name__ == "__main__":
    import sys
    parser = argparse.ArgumentParser(description="Módulo de reescritura y metadatos con Ollama")
    parser.add_argument("--script-path", required=True, help="Ruta al archivo de guion original (.txt)")
    parser.add_argument("--output-script", required=True, help="Ruta de destino para el guion reescrito (.txt)")
    parser.add_argument("--output-meta", required=True, help="Ruta de destino para el JSON de metadatos (.json)")
    parser.add_argument("--gemini-meta", help="Ruta al archivo JSON de metadatos original de Gemini para extraer los hashtags")
    parser.add_argument("--manga", help="Nombre del manga para incluir en el título")
    parser.add_argument("--model", default=OLLAMA_MODEL, help="Modelo de Ollama a utilizar")
    parser.add_argument("--base-url", default=OLLAMA_BASE_URL, help="URL base del servidor de Ollama")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.script_path):
        print(f"Error: No existe el guion de origen en '{args.script_path}'")
        sys.exit(1)
        
    print(f"Iniciando reescritura aislada con Ollama ({args.model})...")
    with open(args.script_path, "r", encoding="utf-8") as f:
        original_script = f.read().strip()
        
    rewritten_script = rewrite_script_by_pages(original_script, model_name=args.model, base_url=args.base_url)
    
    # Extraer hashtags si se provee el json original de Gemini
    gemini_hashtags = ""
    if args.gemini_meta and os.path.exists(args.gemini_meta):
        try:
            with open(args.gemini_meta, "r", encoding="utf-8") as f:
                gemini_data = json.load(f)
            desc_original = gemini_data.get("description", "")
            tags = re.findall(r'#\w+', desc_original)
            if tags:
                gemini_hashtags = " ".join(tags)
                print(f"  [Info] Hashtags extraídos de Gemini: {gemini_hashtags}")
        except Exception as e:
            print(f"  [Warning] No se pudieron extraer los hashtags de Gemini: {e}")
            
    print("Generando metadatos clickbait para el guion...")
    metadata = generate_metadata(
        rewritten_script, 
        model_name=args.model, 
        base_url=args.base_url, 
        original_hashtags=gemini_hashtags,
        manga_name=args.manga
    )
    
    # Crear carpetas de destino si no existen
    os.makedirs(os.path.dirname(os.path.abspath(args.output_script)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.output_meta)), exist_ok=True)
    
    with open(args.output_script, "w", encoding="utf-8") as f:
        f.write(rewritten_script)
        
    with open(args.output_meta, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)
        
    print(f"Proceso completado.")
    print(f"Guion guardado en: {args.output_script}")
    print(f"Metadatos guardados en: {args.output_meta}")
