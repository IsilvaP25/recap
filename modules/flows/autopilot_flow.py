import os
import re
from modules import db_manager
from modules.flows.common import run_pipeline_step, QuotaExceededException, has_pending_pdfs
from modules.utils import limpiar_archivos_intermedios
from modules.api_config import obtener_capitulos_por_parte

def format_cap(num):
    try:
        val = float(num)
        return str(int(val)) if val == int(val) else str(val)
    except (ValueError, TypeError):
        return str(num)

def detectar_y_procesar_maraton(manga_name, p_num, base_proj, uploader_path):
    if p_num != 5:
        return
        
    print(f"\n[AUTO-MARATÓN] ¡Se ha subido la Parte 5 de {manga_name}! Iniciando compilación de las Partes 1 a 5...")
    
    compilation_dir = os.path.join(base_proj, "outputs", manga_name, "FINAL_PUBLICATION", "Maraton_Parte_1_al_5")
    if os.path.exists(os.path.join(compilation_dir, "uploaded.flag")):
        print(f"  [AUTO-MARATÓN] La compilación ya fue creada y subida anteriormente. Saltando.")
        return
        
    import sqlite3
    import shutil
    import subprocess
    import json
    
    # 1. Obtener los detalles de las partes 1 a 5 desde la DB
    db_path = os.path.join(base_proj, "database", "manga_recap.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT part_number, start_chapter, end_chapter 
        FROM pipeline_parts 
        WHERE manga = ? AND part_number <= 5 
        ORDER BY part_number ASC
    """, (manga_name,))
    parts = cursor.fetchall()
    conn.close()
    
    if len(parts) < 5:
        print(f"  [AUTO-MARATÓN] [ERROR] No se encontraron las 5 partes completas en la DB para {manga_name}. Se encontraron {len(parts)}.")
        return
        
    # Verificar y listar archivos de video y obtener las duraciones
    video_files = []
    end_cap = None
    
    for part_num, start_c, end_c in parts:
        part_dir = os.path.join(base_proj, "outputs", manga_name, "FINAL_PUBLICATION", f"Recap_Parte_{part_num}_Caps_{start_c}_al_{end_c}")
        video_path = os.path.join(part_dir, "video_final.mp4")
        if not os.path.exists(video_path):
            print(f"  [AUTO-MARATÓN] [ERROR] No se encontró el video final de la Parte {part_num} en: {video_path}")
            return
        video_files.append((part_num, video_path, start_c, end_c))
        if part_num == 5:
            end_cap = end_c
            
    # Calcular marcas de tiempo (timestamps) acumulativas
    timestamps = []
    current_time = 0.0
    
    def get_video_duration(video_path):
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', video_path
        ]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            print(f"  [AUTO-MARATÓN] [AVISO] Error al obtener duración de {video_path}: {e}")
            return 0.0
            
    def format_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        else:
            return f"{m:02d}:{s:02d}"

    for part_num, video_path, start_c, end_c in video_files:
        time_label = format_time(current_time)
        timestamps.append(f"{time_label} - Parte {part_num}: Caps {start_c} al {end_c}")
        duration = get_video_duration(video_path)
        current_time += duration
        
    timestamps_text = "\n".join(timestamps)
    
    # 2. Generar metadatos clickbait usando la premisa de la Parte 1
    part1_dir = os.path.join(base_proj, "outputs", manga_name, "FINAL_PUBLICATION", f"Recap_Parte_1_Caps_{parts[0][1]}_al_{parts[0][2]}")
    part1_json = os.path.join(part1_dir, "youtube_data.json")
    
    part1_desc = ""
    if os.path.exists(part1_json):
        try:
            with open(part1_json, 'r', encoding='utf-8') as f:
                p1_data = json.load(f)
                part1_desc = p1_data.get('description', '')
        except Exception as e:
            print(f"  [AUTO-MARATÓN] [AVISO] No se pudo leer youtube_data.json de Parte 1: {e}")
            
    # Intentar generar con Gemini
    meta_clickbait = None
    from modules import api_config
    keys = api_config.obtener_api_keys_disponibles()
    
    prompt = f"""
    Eres un experto en YouTube Growth y marketing de anime/manga. Tu tarea es generar los metadatos para una "MEGA COMPILACIÓN" (Maratón) de los capítulos 1 al {end_cap} (Partes 1 a 5) de la serie "{manga_name}".
    
    Para atraer a una NUEVA audiencia, debes reutilizar y reformular la premisa inicial (el gancho de la Parte 1) para que sea extremadamente misterioso, emocionante y clickbait.
    
    Aquí tienes el resumen original de la Parte 1:
    "{part1_desc}"
    
    REGLAS PARA EL TÍTULO (clickbait_title):
    - Máximo 55 caracteres.
    - Muy intrigante, llamativo y en MAYÚSCULAS en sus palabras clave.
    - Debe empezar con '¿' y terminar con '?'.
    - NO debe incluir el nombre del manga en el título para dejar espacio a la intriga (ej: ¿MURIÓ 100 VECES PARA SALVARLA?).
    
    REGLAS PARA LA DESCRIPCIÓN (description):
    - Escribe un texto introductorio nuevo (2-3 líneas) súper enganchador centrado en el misterio del inicio de la historia (Parte 1).
    - Agrega una llamada a la acción clara explicando que este es un MARATÓN completo de las Partes 1 al 5 (Capítulos 1 al {end_cap}) sin interrupciones.
    - Incluye esta lista exacta de marcas de tiempo:
    {timestamps_text}
    
    Devuelve la respuesta en formato JSON limpio con las siguientes llaves:
    {{
       "clickbait_title": "título aquí",
       "description": "descripción completa aquí con marcas de tiempo"
    }}
    """
    
    for i, key in enumerate(keys):
        try:
            client = api_config.obtener_cliente_gemini(force_new_key_index=i)
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            meta_clickbait = json.loads(response.text.strip())
            print(f"  [AUTO-MARATÓN] [Gemini] Metadatos generados con éxito usando clave {i+1}.")
            break
        except Exception as e:
            print(f"  [AUTO-MARATÓN] [AVISO] Falló Gemini con clave {i+1}: {e}")
            
    # Fallback robusto si Gemini falla
    if not meta_clickbait:
        print("  [AUTO-MARATÓN] [FALLBACK] Usando metadatos predefinidos debido a agotamiento de cuota.")
        manga_title_clean = manga_name.replace("_", " ")
        meta_clickbait = {
            "clickbait_title": f"¿EL MARATÓN MÁS ESPERADO DE {manga_title_clean.upper()}? 😱",
            "description": f"¡Disfruta de este maratón completo de las Partes 1 a la 5 (Capítulos 1 al {end_cap}) sin interrupciones! El viaje completo del romance más peligroso y adictivo del manhwa.\n\nMarcas de tiempo:\n{timestamps_text}\n\n#manga #recap #shorts #anime"
        }
        
    meta_clickbait["thumbnail_text"] = "MARATÓN COMPLETO"
    meta_clickbait["manga_folder"] = manga_name
    
    # 3. Concatenar los videos usando FFmpeg
    os.makedirs(compilation_dir, exist_ok=True)
    list_file_path = os.path.join(compilation_dir, "concat_list.txt")
    with open(list_file_path, "w", encoding="utf-8") as lf:
        for _, video_path, _, _ in video_files:
            escaped_path = video_path.replace("\\", "/")
            lf.write(f"file '{escaped_path}'\n")
            
    video_output = os.path.join(compilation_dir, "video_final.mp4")
    print("  [AUTO-MARATÓN] Concatenando videos de las 5 partes...")
    
    cmd_concat = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
        '-i', list_file_path, '-c', 'copy', video_output
    ]
    try:
        subprocess.run(cmd_concat, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print("  [AUTO-MARATÓN] [OK] Video unificado creado.")
    except Exception as e:
        print(f"  [AUTO-MARATÓN] [ERROR] Falló la unificación de video con FFmpeg: {e}")
        return
        
    # 4. Generar la miniatura
    print("  [AUTO-MARATÓN] Generando miniatura...")
    from modules.gemini import thumbnail_generator
    try:
        thumbnail_generator.generate_thumbnail(manga_name, start_cap="1", end_cap=str(end_cap), non_interactive=True)
        generated_thumb = os.path.join(base_proj, "outputs", manga_name, "MINIATURAS", f"MegaRecap_1_al_{end_cap}.png")
        compilation_thumb = os.path.join(compilation_dir, "thumbnail.png")
        if os.path.exists(generated_thumb):
            shutil.copy2(generated_thumb, compilation_thumb)
            print("  [AUTO-MARATÓN] [OK] Miniatura copiada.")
        else:
            part1_thumb = os.path.join(part1_dir, "thumbnail.png")
            if os.path.exists(part1_thumb):
                shutil.copy2(part1_thumb, compilation_thumb)
                print("  [AUTO-MARATÓN] [OK] Miniatura de Parte 1 usada como fallback.")
    except Exception as e:
        print(f"  [AUTO-MARATÓN] [AVISO] No se pudo generar la miniatura: {e}")
        
    # Guardar metadatos JSON
    json_output = os.path.join(compilation_dir, "youtube_data.json")
    with open(json_output, "w", encoding="utf-8") as jf:
        json.dump(meta_clickbait, jf, indent=4, ensure_ascii=False)
        
    # 5. Programar y subir a YouTube
    print("  [AUTO-MARATÓN] Programando subida a YouTube...")
    from modules import db_manager
    proximo_slot = db_manager.get_next_upload_slot()
    
    cmd_upload = [uploader_path, "--video", video_output, "--thumb", os.path.join(compilation_dir, "thumbnail.png"), "--json", json_output, "--manga", manga_name]
    if proximo_slot:
        cmd_upload += ["--schedule", proximo_slot]
        
    from modules.flows.common import run_pipeline_step
    if run_pipeline_step("Upload YouTube Maratón", cmd_upload):
        db_manager.update_last_upload_date(proximo_slot)
        with open(os.path.join(compilation_dir, "uploaded.flag"), "w") as flag:
            flag.write(f"Uploaded successfully at slot: {proximo_slot}")
        print(f"  [AUTO-MARATÓN] [OK] Compilación de las Partes 1 a 5 programada para: {proximo_slot}.")
    else:
        print("  [AUTO-MARATÓN] [ERROR] Falló la subida de la compilación.")

def iniciar_flujo():
    print("\n" + "!"*50)
    print("      --- INICIANDO PIPELINE AUTO-PILOT ---")
    print("!"*50)
    db_manager.init_db()
    
    try:
        base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import sys
        if base_proj not in sys.path:
            sys.path.append(base_proj)
        
        pdf_base = os.path.join(base_proj, "pdf_storage")
        db_path = os.path.join(base_proj, "database", "manga_recap.db")
        
        # Preguntar si solo se desea subir los vídeos pendientes
        solo_subidas = input("¿Deseas realizar ÚNICAMENTE la subida de vídeos largos pendientes? (s/n): ").strip().lower() == 's'
        
        if solo_subidas:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT manga FROM pipeline_parts WHERE is_uploaded = 0 AND status = 'completed'")
            mangas_disponibles = sorted([row[0] for row in cursor.fetchall()])
            conn.close()
            
            if not mangas_disponibles:
                print("No hay ningún vídeo largo pendiente de subida en la base de datos.")
                return
        else:
            mangas_disponibles = sorted([
                d for d in os.listdir(pdf_base) 
                if os.path.isdir(os.path.join(pdf_base, d)) and has_pending_pdfs(d, pdf_base, db_path)
            ])
            
            if not mangas_disponibles:
                print("No hay mangas en pdf_storage con capítulos suficientes para procesar.")
                return
    
        print(f"\nMangas disponibles para {'Subida de Pendientes' if solo_subidas else 'Auto-Pilot'}:")
        for i, m in enumerate(mangas_disponibles, 1):
            print(f"{i}. {m.replace('_', ' ')}")
        print(f"{len(mangas_disponibles) + 1}. PROCESAR TODOS")
        
        sel = input("\nSelecciona una o varias opciones (ej: 1,3,4): ")
        if not sel.strip(): return
        
        # Lógica de selección múltiple
        if str(len(mangas_disponibles) + 1) in sel.split():
            mangas_a_procesar = mangas_disponibles
        else:
            indices = [int(i) for i in re.findall(r'\d+', sel)]
            mangas_a_procesar = [mangas_disponibles[i-1] for i in indices if 0 < i <= len(mangas_disponibles)]
        
        if not mangas_a_procesar:
            print("Selección no válida.")
            return
    
        # El uploader está en la raíz (end to end/api/...)
        root_workspace = os.path.dirname(base_proj)
        uploader_path = os.path.join(root_workspace, "modules", "subida", "youtube_uploader.py")
    
        for manga_name in mangas_a_procesar:
            print(f"\n>>> TRABAJANDO EN: {manga_name.replace('_', ' ')}")
            
            while True:
                # Reservamos el slot si detectamos que hay algo que subir
                proximo_slot = None
    
                # --- 2. DETECCIÓN DE PARTES LARGAS PENDIENTES ---
                pending = db_manager.get_pending_uploads(manga_name)
                if pending:
                    p_num, start_c, end_c = pending[0]
                    print(f"\n  [PENDIENTE] Detectada Parte {p_num} (Caps {start_c}-{end_c}) sin subir.")
                    
                    # Asegurar video consolidado
                    publish_dir = os.path.join(base_proj, "outputs", manga_name, "FINAL_PUBLICATION", f"Recap_Parte_{p_num}_Caps_{start_c}_al_{end_c}")
                    video_p = os.path.join(publish_dir, "video_final.mp4")
                    thumb_p = os.path.join(publish_dir, "thumbnail.png")
                    json_p = os.path.join(publish_dir, "youtube_data.json")
                    
                    if not os.path.exists(video_p) or not os.path.exists(thumb_p) or not os.path.exists(json_p):
                        print(f"  [ALERTA] Faltan archivos para la Parte {p_num}. Reconstruyendo...")
                        success_rebuild = True
                        if not os.path.exists(json_p):
                            if not run_pipeline_step("Metadatos", ["modules/gemini/metadata_generator.py", "--manga", manga_name, "--start", str(start_c), "--end", str(end_c), "--part", str(p_num)]):
                                success_rebuild = False
                        if not os.path.exists(thumb_p):
                            if not run_pipeline_step("Miniatura", ["modules/gemini/thumbnail_generator.py", "--manga", manga_name, "--start", str(start_c), "--end", str(end_c), "--auto"]):
                                success_rebuild = False
                                
                        if not success_rebuild:
                            print(f"  [ERROR] Falló la reconstrucción de activos para la Parte {p_num}. Saltando subida...")
                            break
                            
                        if not run_pipeline_step("Consolidar", ["modules/consolidator.py", "--manga", manga_name, "--start", str(start_c), "--end", str(end_c), "--part", str(p_num)]):
                            print(f"  [ERROR] Falló la consolidación para la Parte {p_num}. Saltando subida...")
                            break
    
                    if not os.path.exists(video_p):
                        print(f"  [ERROR] El archivo de video no existe: {video_p}. Saltando subida...")
                        break
                    if not os.path.exists(thumb_p):
                        print(f"  [ERROR] El archivo de miniatura no existe: {thumb_p}. Saltando subida...")
                        break
                    if not os.path.exists(json_p):
                        print(f"  [ERROR] El archivo de metadatos no existe: {json_p}. Saltando subida...")
                        break
                    
                    if not proximo_slot: proximo_slot = db_manager.get_next_upload_slot()
                    
                    cmd = [uploader_path, "--video", video_p, "--thumb", thumb_p, "--json", json_p, "--manga", manga_name]
                    if proximo_slot:
                        cmd += ["--schedule", proximo_slot]
                        
                    if run_pipeline_step("Upload YouTube", cmd):
                        db_manager.mark_as_uploaded(manga_name, p_num, "auto_uploaded")
                        db_manager.update_last_upload_date(proximo_slot)
                        print(f"  [OK] Parte {p_num} programada para {proximo_slot}.")
                        # DETECTAR Y PROCESAR MARATÓN
                        detectar_y_procesar_maraton(manga_name, p_num, base_proj, uploader_path)
                        continue 
                    else:
                        break
                        
                if solo_subidas:
                    print(f"  [OK] Todos los vídeos pendientes de {manga_name} han sido subidos.")
                    break
    
                # 3. Descubrimiento de videos físicos y Producción Nueva
                last_part, last_cap_done = db_manager.get_last_part(manga_name)
                last_cap_done_float = float(last_cap_done) if last_cap_done else 0.0
                pdf_dir = os.path.join(pdf_base, manga_name)
                if not os.path.exists(pdf_dir):
                    break
                
                def extract_num(fn):
                    m = re.search(r'(\d+\.\d+|\d+)', fn)
                    return float(m.group(1)) if m else 0.0
                    
                all_pdfs = sorted([f for f in os.listdir(pdf_dir) if f.endswith(".pdf")], key=extract_num)
                avail_caps = []
                for f in all_pdfs:
                    m = re.search(r'(\d+\.\d+|\d+)', f)
                    if m: avail_caps.append(float(m.group(1)))
                avail_caps = [c for c in avail_caps if c > last_cap_done_float]
                
                if not avail_caps:
                    print(f"  [FIN] Todo al día para {manga_name}.")
                    break
                
                chunk = avail_caps[:obtener_capitulos_por_parte()]
                if not chunk:
                    break
                    
                start_c = chunk[0]
                end_c = chunk[-1]
                
                mega_recap_src = os.path.join(base_proj, "outputs", manga_name, "VIDEOS", f"MegaRecap_{format_cap(start_c)}_al_{format_cap(end_c)}.mp4")
                
                if os.path.exists(mega_recap_src):
                    print(f"  [DESCUBRIMIENTO] Video detectado para Caps {format_cap(start_c)}-{format_cap(end_c)}. Registrando...")
                    db_manager.save_pipeline_part(manga_name, last_part + 1, format_cap(start_c), format_cap(end_c))
                    continue
                
                print(f"  [INFO] Procesando bloque {format_cap(start_c)}-{format_cap(end_c)} ({len(chunk)} capítulos disponibles).")
                
                # PASO A: INTELIGENCIA ARTIFICIAL (Guiones, Traducciones y Metadatos)
                # Esto agota los tokens de Gemini al inicio para asegurar que tenemos todo el texto listo
                print(f"  [FASE IA] Iniciando generación de textos para {len(chunk)} capítulos...")
                success_ia = True
                for cap in chunk:
                    pdf_path = os.path.join(pdf_dir, f"Capitulo_{format_cap(cap)}.pdf")
                    if not os.path.exists(pdf_path): pdf_path = os.path.join(pdf_dir, f"{format_cap(cap)}.pdf")
                    mode_sw = "full"
                    
                    if not run_pipeline_step(f"Guion {format_cap(cap)}", ["modules/gemini/manga_scriptwriter.py", "--manga", manga_name, "--chapter", format_cap(cap), "--pdf", pdf_path, "--mode", mode_sw]):
                        success_ia = False
                        break
                    if not run_pipeline_step(f"Traducción {format_cap(cap)}", ["modules/guion_metadatos/script_translator.py", "--manga", manga_name, "--chapter", format_cap(cap)]):
                        success_ia = False
                        break
                
                if not success_ia:
                    print(f"  [ERROR] Falló la fase de Inteligencia Artificial para {manga_name}. Abortando este bloque.")
                    break
                    
                if not run_pipeline_step("Metadatos", ["modules/gemini/metadata_generator.py", "--manga", manga_name, "--start", format_cap(start_c), "--end", format_cap(end_c), "--part", str(last_part + 1)]):
                    print(f"  [ERROR] Falló el paso de Metadatos para {manga_name}. Abortando este bloque.")
                    break
    
                # PASO B: PRODUCCIÓN TÉCNICA (Audio y Video)
                print(f"  [FASE PRODUCCIÓN] Iniciando renderizado de archivos multimedia...")
                success_prod = True
                for cap in chunk:
                    pdf_path = os.path.join(pdf_dir, f"Capitulo_{format_cap(cap)}.pdf")
                    if not os.path.exists(pdf_path): pdf_path = os.path.join(pdf_dir, f"{format_cap(cap)}.pdf")
                    mode_sw = "full"
    
                    if not run_pipeline_step(f"Audio {format_cap(cap)}", ["modules/audio/audio_generator.py", "--manga", manga_name, "--chapter", format_cap(cap), "--mode", mode_sw]):
                        success_prod = False
                        break
                    if not run_pipeline_step(f"Video {format_cap(cap)}", ["modules/video/video_assembler.py", "--manga", manga_name, "--chapter", format_cap(cap), "--pdf", pdf_path, "--mode", "full"]):
                        success_prod = False
                        break
                
                if not success_prod:
                    print(f"  [ERROR] Falló la fase de Producción Técnica para {manga_name}. Abortando este bloque.")
                    break
    
                if not run_pipeline_step("Mega Recap", ["modules/video/video_assembler.py", "--manga", manga_name, "--pdf", "none", "--master", "--chapters"] + [format_cap(c) for c in chunk]):
                    print(f"  [ERROR] Falló la creación del Mega Recap para {manga_name}. Abortando este bloque.")
                    break
                if not run_pipeline_step("Miniatura", ["modules/gemini/thumbnail_generator.py", "--manga", manga_name, "--start", format_cap(start_c), "--end", format_cap(end_c), "--auto"]):
                    print(f"  [ERROR] Falló la generación de la Miniatura para {manga_name}. Abortando este bloque.")
                    break
                if not run_pipeline_step("Consolidar", ["modules/consolidator.py", "--manga", manga_name, "--start", format_cap(start_c), "--end", format_cap(end_c), "--part", str(last_part + 1)]):
                    print(f"  [ERROR] Falló la consolidación para {manga_name}. Abortando este bloque.")
                    break
                limpiar_archivos_intermedios(manga_name, chunk)
                
                last_part += 1
                db_manager.save_pipeline_part(manga_name, last_part, format_cap(start_c), format_cap(end_c))
                
                # SUBIDA CON PROGRAMACIÓN
                publish_dir = os.path.join(base_proj, "outputs", manga_name, "FINAL_PUBLICATION", f"Recap_Parte_{last_part}_Caps_{format_cap(start_c)}_al_{format_cap(end_c)}")
                video_p = os.path.join(publish_dir, "video_final.mp4")
                thumb_p = os.path.join(publish_dir, "thumbnail.png")
                json_p = os.path.join(publish_dir, "youtube_data.json")
                
                if not proximo_slot: proximo_slot = db_manager.get_next_upload_slot()
                cmd = [uploader_path, "--video", video_p, "--thumb", thumb_p, "--json", json_p, "--manga", manga_name]
                if proximo_slot:
                    cmd += ["--schedule", proximo_slot]
                    
                if run_pipeline_step("Upload YouTube", cmd):
                    db_manager.mark_as_uploaded(manga_name, last_part, "auto_uploaded")
                    db_manager.update_last_upload_date(proximo_slot)
                    # DETECTAR Y PROCESAR MARATÓN
                    detectar_y_procesar_maraton(manga_name, last_part, base_proj, uploader_path)
    except QuotaExceededException as e:
        print(f"\n❌ [CUOTA EXCEDIDA] Se detiene la ejecución del Auto-Pilot: {e}")
