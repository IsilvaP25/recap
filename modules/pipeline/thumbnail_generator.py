import os
import json
import argparse
import sys
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from google import genai
from dotenv import load_dotenv

# Asegurar que se puede importar desde la raíz del proyecto
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.stdout.reconfigure(encoding='utf-8')

# Configuración
load_dotenv()

def generar_prompt_con_gemini(manga_title, summary):
    try:
        from modules import api_config
        client = api_config.obtener_cliente_gemini()
        modelo = api_config.nombre_modelo_ia()
    except Exception:
        from modules import token_monitor
        if token_monitor.validar_acceso_gemini():
            from modules import api_config
            client = api_config.obtener_cliente_gemini()
            modelo = api_config.nombre_modelo_ia()
        else:
            return None

    prompt_ia = (
        f"Actúa como un experto en miniaturas y CTR de YouTube.\n"
        f"Diseña un prompt altamente descriptivo en INGLÉS para un generador de imágenes de IA (como Imagen 3/4 o Flux) "
        f"para una miniatura basada en el manga:\n"
        f"Título: {manga_title}\n"
        f"Sinopsis: {summary}\n\n"
        f"REGLAS DEL PROMPT A GENERAR:\n"
        f"1. Estilo visual: Anime vibrante, iluminación cinematográfica, alta calidad, 8k, impacto emocional.\n"
        f"2. Composición: Describe una escena dramática de contraste o ruptura relacionada con la sinopsis.\n"
        f"3. Texto de Clickbait en ESPAÑOL: En la miniatura debe aparecer un texto en español llamativo, impactante y grande, estilo YouTube. Describe esto detalladamente en el prompt de la imagen para que la IA lo dibuje (ej. 'with big bold colorful comic-style text overlay that reads: ¡AL FIN LIBRE!'). Todo lo que se escriba en la imagen debe ir en español. El prompt en inglés debe especificar de forma explícita que este texto/palabras escritas deben ubicarse únicamente en la mitad derecha de la imagen (si se dividiera la imagen verticalmente en dos mitades o columnas iguales, el texto debe estar en la mitad o columna derecha).\n"
        f"4. Devuelve ÚNICAMENTE el prompt de la imagen final en inglés. Sin introducciones ni comentarios adicionales."
    )
    
    intentos = 0
    while intentos < 3:
        try:
            response = client.models.generate_content(
                model=modelo,
                contents=prompt_ia
            )
            return response.text.strip()
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                print("  [!] Cuota agotada en la API Key actual. Rotando llaves...")
                from modules import token_monitor
                if token_monitor.validar_acceso_gemini():
                    from modules import api_config
                    client = api_config.obtener_cliente_gemini()
                    modelo = api_config.nombre_modelo_ia()
                    intentos += 1
                    continue
                else:
                    print("  [ERROR] No hay más API Keys con cuota disponible.")
                    break
            else:
                print(f"  [ERROR IA PROMPT] {e}")
                break
    return None

def download_cover(manga_name, manga_id):
    """Descarga la portada oficial del manga desde la API."""
    from modules import manga_search
    print(f"  [COVER] Buscando portada oficial para ID: {manga_id}...")
    details = manga_search.obtener_detalles_completos(manga_id)
    thumb_url = details.get("thumb")
    
    if not thumb_url:
        print("  [AVISO] No se encontró URL de portada en la API.")
        return None
        
    base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cover_dir = os.path.join(base_proj, "outputs", manga_name, "COVER")
    os.makedirs(cover_dir, exist_ok=True)
    cover_path = os.path.join(cover_dir, "official_cover.webp")
    
    try:
        res = requests.get(thumb_url, stream=True)
        if res.status_code == 200:
            with open(cover_path, "wb") as f:
                for chunk in res.iter_content(1024):
                    f.write(chunk)
            print(f"  [OK] Portada descargada: {cover_path}")
            return cover_path
    except Exception as e:
        print(f"  [ERROR] Al descargar portada: {e}")
    return None

def generate_thumbnail(manga_name, start_cap, end_cap, non_interactive=False):
    base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out_dir = os.path.join(base_proj, "outputs", manga_name, "MINIATURAS")
    out_path = os.path.join(out_dir, f"MegaRecap_{start_cap}_al_{end_cap}.png")
    
    if os.path.exists(out_path):
        print(f"  [OK] Miniatura ya existe en: {out_path}. Saltando generación.")
        return True

    print(f"\n--- MOTOR DE DISEÑO PRO: Generando Miniatura para {manga_name} ---")
    
    # 1. Obtener ID y Resumen del manga desde la base de datos (Búsqueda flexible)
    import sqlite3
    db_path = os.path.join(base_proj, "database", "manga_recap.db")
    manga_id = None
    summary = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Buscamos por coincidencia parcial para evitar líos con apóstrofes o guiones
        clean_name = manga_name.replace("_", "%").replace(" ", "%")
        cursor.execute("SELECT id, resumen FROM mangas WHERE titulo LIKE ?", (f"%{clean_name}%",))
        row = cursor.fetchone()
        if row: 
            manga_id = row[0]
            summary = row[1]
        conn.close()
    except Exception as e:
        print(f"  [ERROR DB] {e}")

    # --- FLUJO INTERACTIVO DE MINIATURA CON IA ---
    # Generar y mostrar prompt en terminal para que el usuario pueda crear la imagen externamente
    prompt_visual = None
    if summary and not non_interactive:
        print("  [+] Generando sugerencia de prompt visual con Gemini...")
        prompt_visual = generar_prompt_con_gemini(manga_name.replace("_", " "), summary)

    if prompt_visual and not non_interactive:
        print("\n" + "="*80)
        print(">>> PROMPT VISUAL GENERADO PARA TU MINIATURA (Copiar y generar por separado) <<<")
        print("="*80)
        print(prompt_visual)
        print("="*80)
        print("\n[Instrucciones]:")
        print("1. Copia el prompt anterior y utilízalo en tu herramienta de IA preferida (Google AI Studio, DALL-E, etc.)")
        print("2. Descarga la imagen generada en tu ordenador.")
        print("3. Introduce a continuación la ruta de la imagen para guardarla en el proyecto.")
        print("   (Presiona ENTER sin escribir nada para omitir y generar la miniatura clásica con Pillow)\n")
        
        try:
            user_path = input("Ruta de la imagen descargada: ").strip()
            
            # Limpiar comillas si arrastró el archivo a la terminal
            if user_path.startswith('"') and user_path.endswith('"'):
                user_path = user_path[1:-1]
            elif user_path.startswith("'") and user_path.endswith("'"):
                user_path = user_path[1:-1]
                
            if user_path and os.path.exists(user_path):
                os.makedirs(out_dir, exist_ok=True)
                # Copiar y guardar como imagen.png (base sin editar)
                custom_base = os.path.join(out_dir, "imagen.png")
                img = Image.open(user_path)
                img.save(custom_base, "PNG")
                print(f"\n[OK] ¡Imagen base guardada en: {custom_base}! Procediendo a editar con el diseño del texto...\n")
            elif user_path:
                print(f"\n[AVISO] Ruta '{user_path}' no válida o archivo inexistente.")
                print("Se procederá a generar la miniatura por defecto...")
            else:
                print("\n[Omitido] Generando miniatura por defecto con Pillow...")
        except Exception as e:
            print(f"\n[ERROR] Al procesar la entrada de ruta: {e}")
            print("Se procederá a generar la miniatura por defecto...")

    # 2. Determinar si existe base personalizada
    def buscar_imagen_base(d, start=None, end=None):
        if not os.path.exists(d): return None
        if start is not None and end is not None:
            # Buscar coincidencia exacta por capítulo
            for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                for prefix in ['imagen_', 'base_', '']:
                    name = f"{prefix}{start}_al_{end}{ext}"
                    path = os.path.join(d, name)
                    if os.path.exists(path):
                        return path
        # Fallback a cualquier imagen que no empiece con MegaRecap_
        for f in os.listdir(d):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) and not f.startswith("MegaRecap_"):
                return os.path.join(d, f)
        return None
        
    custom_base = buscar_imagen_base(out_dir, start_cap, end_cap)
    is_custom = custom_base is not None
    
    # 3. DISEÑO CON PILLOW (1280x720)
    try:
        canvas_w, canvas_h = 1280, 720
        
        if is_custom:
            print(f"  [DESIGN] Usando imagen personalizada como base: {custom_base}")
            img = Image.open(custom_base).convert("RGB")
            # Redimensionar y recortar al centro manteniendo relación de aspecto
            img_ratio = img.width / img.height
            target_ratio = canvas_w / canvas_h
            if img_ratio > target_ratio:
                # Más ancha
                new_h = canvas_h
                new_w = int(img.width * (canvas_h / img.height))
                img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                left = (new_w - canvas_w) // 2
                thumbnail = img_resized.crop((left, 0, left + canvas_w, canvas_h))
            else:
                # Más alta
                new_w = canvas_w
                new_h = int(img.height * (canvas_w / img.width))
                img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                top = (new_h - canvas_h) // 2
                thumbnail = img_resized.crop((0, top, canvas_w, top + canvas_h))
        else:
            # Flujo por defecto: Cargar portada oficial y crear fondo desenfocado
            cover_path = None
            local_cover = os.path.join(base_proj, "outputs", manga_name, "COVER", "official_cover.webp")
            
            if os.path.exists(local_cover):
                print(f"  [OK] Portada local encontrada: {local_cover}")
                cover_path = local_cover
            elif manga_id:
                cover_path = download_cover(manga_name, manga_id)
            
            if not cover_path:
                print("  [ERROR CRÍTICO] No se encontró portada oficial en local ni en la API.")
                print("  Para continuar, coloca la portada manualmente en la carpeta COVER del manga.")
                sys.exit(1)
                
            thumbnail = Image.new('RGB', (canvas_w, canvas_h), (20, 20, 20))
            img_cover = Image.open(cover_path).convert("RGB")
            
            # --- FONDO (Efecto Cinemático) ---
            bg_scale = canvas_w / img_cover.width
            bg_img = img_cover.resize((canvas_w, int(img_cover.height * bg_scale)), Image.Resampling.LANCZOS)
            bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=15))
            bg_top = (bg_img.height - canvas_h) // 2
            bg_img = bg_img.crop((0, bg_top, canvas_w, bg_top + canvas_h))
            overlay = Image.new('RGB', (canvas_w, canvas_h), (0, 0, 0))
            bg_img = Image.blend(bg_img, overlay, 0.5)
            thumbnail.paste(bg_img, (0, 0))
            
            # --- IMAGEN PRINCIPAL (Portada a la derecha) ---
            c_h = canvas_h - 100
            c_w = int(img_cover.width * (c_h / img_cover.height))
            img_cover_main = img_cover.resize((c_w, c_h), Image.Resampling.LANCZOS)
            border = 5
            img_with_border = Image.new('RGB', (c_w + border*2, c_h + border*2), (255, 255, 255))
            img_with_border.paste(img_cover_main, (border, border))
            
            pos_x = canvas_w - c_w - 80
            pos_y = 50
            thumbnail.paste(img_with_border, (pos_x, pos_y))

        # --- TEXTO (Título, Parte y Capítulos) ---
        draw = ImageDraw.Draw(thumbnail)
        
        # Cargar fuentes
        font_path = "C:/Windows/Fonts/impact.ttf"
        if not os.path.exists(font_path): font_path = "arial.ttf"
        
        # Intentar obtener el número de parte dinámicamente de la DB
        part_num = 1
        try:
            from modules.pipeline import db_manager
            last_part, _ = db_manager.get_last_part(manga_name)
            part_num = last_part + 1
        except Exception as e:
            print(f"  [AVISO DB] No se pudo obtener la parte de la DB: {e}")
            
        # Intentar obtener el título del video de metadata.json
        video_title = manga_name.replace("_", " ").upper()
        video_title_sub = ""
        
        metadata_path = os.path.join(base_proj, "outputs", manga_name, "Scripts", f"Capitulo_{start_cap}_metadata.json")
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                    clickbait = meta.get("clickbait_title", "")
                    if clickbait:
                        clean_title = clickbait.split('#')[0].split('(')[0].split('|')[0].strip()
                        words = clean_title.split()
                        if len(words) > 4:
                            mid = len(words) // 2
                            video_title = " ".join(words[:mid]).upper()
                            video_title_sub = " ".join(words[mid:]).upper()
                        else:
                            video_title = clean_title.upper()
            except Exception as e:
                print(f"  [AVISO] No se pudo leer clickbait del metadata: {e}")
                
        def draw_text_with_shadow(draw, position, text, font, fill_color, shadow_color, shadow_offset=4):
            x, y = position
            draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color)
            draw.text((x, y), text, font=font, fill=fill_color)

        if is_custom:
            # Posicionamiento optimizado para la imagen personalizada completa
            try:
                font_title = ImageFont.truetype(font_path, 80)
                font_sub = ImageFont.truetype(font_path, 60)
                font_part = ImageFont.truetype(font_path, 50)
                font_caps = ImageFont.truetype(font_path, 90)
            except:
                font_title = font_sub = font_part = font_caps = ImageFont.load_default()
                
            # 1. PARTE X (Dorado/Amarillo, esquina superior izquierda)
            draw_text_with_shadow(draw, (50, 40), f"PARTE {part_num}", font_part, (255, 215, 0), (0, 0, 0))
            
            # 2. Título de dos líneas
            draw_text_with_shadow(draw, (50, 110), video_title, font_title, (255, 255, 255), (0, 0, 0), shadow_offset=6)
            if video_title_sub:
                draw_text_with_shadow(draw, (50, 200), video_title_sub, font_sub, (255, 255, 255), (0, 0, 0), shadow_offset=5)
                
            # 3. CAPS X-Y (Caja roja de alto impacto en la esquina inferior izquierda)
            caps_text = f"CAPS {start_cap}-{end_cap}"
            draw.rectangle([40, 560, 420, 670], fill=(230, 0, 0))
            draw.text((60, 565), caps_text, font=font_caps, fill=(255, 255, 255))
        else:
            # Posicionamiento clásico para portada lateral
            try:
                font_title = ImageFont.truetype(font_path, 80)
                font_caps = ImageFont.truetype(font_path, 120)
                font_part = ImageFont.truetype(font_path, 50)
            except:
                font_title = font_caps = font_part = ImageFont.load_default()
                
            # Título recortado si es muy largo para que no pise la portada a la derecha
            display_title = video_title
            if len(display_title) > 22:
                display_title = display_title[:19] + "..."
            draw_text_with_shadow(draw, (50, 100), display_title, font_title, (255, 255, 255), (0, 0, 0))
            
            draw_text_with_shadow(draw, (50, 200), f"PARTE {part_num}", font_part, (255, 215, 0), (0, 0, 0))
            
            caps_text = f"CAPS {start_cap}-{end_cap}"
            draw.rectangle([40, 350, 600, 500], fill=(255, 0, 0))
            draw.text((60, 360), caps_text, font=font_caps, fill=(255, 255, 255))

        # 4. Guardar Resultado Final
        out_dir = os.path.join(base_proj, "outputs", manga_name, "MINIATURAS")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"MegaRecap_{start_cap}_al_{end_cap}.png")
        thumbnail.save(out_path)
        
        print(f"  [OK] Miniatura {'PERSONALIZADA' if is_custom else 'CLÁSICA'} generada y guardada en: {out_path}")
        return True
        
    except Exception as e:
        print(f"  [ERROR] Al diseñar miniatura: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manga", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--auto", action="store_true")
    args = parser.parse_args()
    
    generate_thumbnail(args.manga, args.start, args.end, non_interactive=args.auto)
