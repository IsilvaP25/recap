import os
from modules import db_manager
from modules.flows.common import run_pipeline_step, ApiKeyExhaustedException, QuotaExceededException, has_pending_pdfs
from modules.utils import limpiar_archivos_intermedios
from modules.api_config import obtener_capitulos_por_parte

def iniciar_flujo():
    print("\n--- FASE 3: MOTOR DE PRODUCCIÓN 3.0 ---")
    db_manager.init_db()
    
    # Ruta absoluta al proyecto
    base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pdf_base = os.path.join(base_proj, "pdf_storage")
    
    if not os.path.exists(pdf_base):
        print(f"No se encontró la carpeta {pdf_base}. ¿Ya convertiste los mangas?")
        return

    db_path = os.path.join(base_proj, "database", "manga_recap.db")
    mangas_disponibles = sorted([
        d for d in os.listdir(pdf_base)
        if os.path.isdir(os.path.join(pdf_base, d)) and has_pending_pdfs(d, pdf_base, db_path)
    ])
    if not mangas_disponibles:
        print("No hay PDFs disponibles para procesar (todos sus capítulos ya tienen video hecho).")
        return

    for i, m in enumerate(mangas_disponibles, 1):
        print(f"{i}. {m.replace('_', ' ')}")
    print(f"{len(mangas_disponibles) + 1}. PROCESAR TODOS")
    
    sel = input("\nSelecciona uno o varios mangas (ej: 1,3 o 4): ")
    if not sel.strip(): return
    
    if str(len(mangas_disponibles) + 1) in sel.split() or sel.strip() == str(len(mangas_disponibles) + 1):
        mangas_a_procesar = mangas_disponibles
    else:
        import re
        indices = [int(x) for x in re.findall(r'\d+', sel)]
        mangas_a_procesar = [mangas_disponibles[idx-1] for idx in indices if 0 < idx <= len(mangas_disponibles)]
        
    if not mangas_a_procesar:
        print("Selección no válida.")
        return

    solo_ia = False
    prompted_blocks = set()

    def format_cap(num):
        try:
            val = float(num)
            return str(int(val)) if val == int(val) else str(val)
        except (ValueError, TypeError):
            return str(num)

    def buscar_imagen_base(d):
        if not os.path.exists(d): return None
        for f in os.listdir(d):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) and not f.startswith("MegaRecap_"):
                return os.path.join(d, f)
        return None

    # --- FASE PREVIA: COMPROBACIÓN ANTICIPADA DE MINIATURAS ---
    print("\n" + "="*60)
    print("      --- COMPROBACIÓN PREVIA DE MINIATURAS ---")
    print("="*60)
    
    for manga_name in mangas_a_procesar:
        cap_limit = obtener_capitulos_por_parte()
        last_part, last_cap_done = db_manager.get_last_part(manga_name)
        last_cap_done_float = float(last_cap_done) if last_cap_done else 0.0
        
        import re
        def extract_num(fn):
            m = re.search(r'(\d+\.\d+|\d+)', fn)
            return float(m.group(1)) if m else 0.0
            
        pdf_dir = os.path.join(pdf_base, manga_name)
        if not os.path.exists(pdf_dir):
            continue
        all_pdfs = sorted([f for f in os.listdir(pdf_dir) if f.endswith(".pdf")], key=extract_num)
        all_pdf_nums = [extract_num(f) for f in all_pdfs]
        
        if last_cap_done_float in all_pdf_nums:
            start_idx = all_pdf_nums.index(last_cap_done_float) + 1
        else:
            start_idx = 0
            for idx, val in enumerate(all_pdf_nums):
                if val > last_cap_done_float:
                    start_idx = idx
                    break
                    
        chapters_to_process = all_pdf_nums[start_idx:]
        if not chapters_to_process or len(chapters_to_process) < cap_limit:
            continue
            
        chunk = chapters_to_process[:cap_limit]
        start_c, end_c = chunk[0], chunk[-1]
        
        # Verificar miniatura
        out_dir = os.path.join(base_proj, "outputs", manga_name, "MINIATURAS")
        out_path = os.path.join(out_dir, f"MegaRecap_{format_cap(start_c)}_al_{format_cap(end_c)}.png")
        
        base_detectada = buscar_imagen_base(out_dir)
        if not os.path.exists(out_path) and not base_detectada:
            print(f"\n[MINIATURA FALTANTE] Manga: {manga_name.replace('_', ' ')}")
            print(f"  Siguiente Bloque: Caps {format_cap(start_c)} al {format_cap(end_c)}")
            
            # Intentar obtener el prompt del Short desde la DB
            _, short_prompt = db_manager.get_short_script(manga_name)
            
            # Si no existe, generamos un prompt basado en el resumen general como fallback
            if not short_prompt:
                print("  [+] Generando sugerencia de prompt visual con Gemini...")
                import sqlite3
                summary = None
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    clean_name = manga_name.replace("_", "%").replace(" ", "%")
                    cursor.execute("SELECT resumen FROM mangas WHERE titulo LIKE ?", (f"%{clean_name}%",))
                    row = cursor.fetchone()
                    if row:
                        summary = row[0]
                    conn.close()
                except Exception as e:
                    print(f"  [ERROR DB] {e}")
                
                if summary:
                    try:
                        from modules.pipeline.thumbnail_generator import generar_prompt_con_gemini
                        short_prompt = generar_prompt_con_gemini(manga_name.replace("_", " "), summary)
                    except Exception as e:
                        print(f"  [ERROR SUGERENCIA] No se pudo conectar con la IA: {e}")
            
            if short_prompt:
                print("\n" + "="*80)
                print(f">>> PROMPT SUGERIDO PARA EL MANGA: {manga_name.replace('_', ' ').upper()} <<<")
                print("="*80)
                print(short_prompt)
                print("="*80)
                print("\n[Instrucciones]:")
                print("1. Copia el prompt anterior y utilízalo en tu herramienta de IA preferida.")
                print("2. Descarga la imagen y guárdala en la carpeta MINIATURAS del manga:")
                print(f"   {out_dir}")
                print("3. Confirma a continuación si ya la has colocado allí.\n")
                
                try:
                    os.makedirs(out_dir, exist_ok=True)
                    confirm = input("¿Has guardado ya la imagen en la carpeta MINIATURAS? (s/n): ").strip().lower()
                    if confirm == 's':
                        base_detectada = buscar_imagen_base(out_dir)
                        if base_detectada:
                            print(f"\n✅ [OK] ¡Imagen detectada con éxito: {os.path.basename(base_detectada)}!\n")
                        else:
                            print("\n[AVISO] No se detectó ninguna imagen en la carpeta. Se continuará con el flujo.")
                    else:
                        print("\n[Omitido] Se continuará. La miniatura se diseñará por defecto con la portada oficial al final.")
                except Exception as e:
                    print(f"\n[ERROR] Al procesar la confirmación: {e}. Continuando...")
            
            prompted_blocks.add(f"{manga_name}_{format_cap(start_c)}_{format_cap(end_c)}")

    print("\n" + "="*60)
    print("      --- INICIANDO FASE DE PRODUCCIÓN ---")
    print("="*60)

    try:
        for manga_name in mangas_a_procesar:
            print(f"\n>>> EMPEZANDO PROCESAMIENTO DE: {manga_name.replace('_', ' ')} <<<")
            cap_offset = 0
            while True:
                cap_limit = obtener_capitulos_por_parte()
                last_part, last_cap_done = db_manager.get_last_part(manga_name)
                last_cap_done_float = float(last_cap_done) if last_cap_done else 0.0
                current_part = last_part + 1 + (cap_offset // cap_limit)

                import re
                def extract_num(fn):
                    m = re.search(r'(\d+\.\d+|\d+)', fn)
                    return float(m.group(1)) if m else 0.0
                    
                pdf_dir = os.path.join(pdf_base, manga_name)
                all_pdfs = sorted([f for f in os.listdir(pdf_dir) if f.endswith(".pdf")], key=extract_num)
                all_pdf_nums = [extract_num(f) for f in all_pdfs]
                
                if last_cap_done_float in all_pdf_nums:
                    start_idx = all_pdf_nums.index(last_cap_done_float) + 1
                else:
                    start_idx = 0
                    for idx, val in enumerate(all_pdf_nums):
                        if val > last_cap_done_float:
                            start_idx = idx
                            break
                            
                start_idx += cap_offset
                chapters_to_process = all_pdf_nums[start_idx:]
                
                if not chapters_to_process or len(chapters_to_process) < cap_limit:
                    print(f"No hay suficientes capítulos (mínimo {cap_limit}) para un nuevo bloque en {manga_name}.")
                    break

                chunk = chapters_to_process[:cap_limit]
                start_c, end_c = chunk[0], chunk[-1]

                # --- PETICIÓN DE MINIATURA DENTRO DEL BUCLE (SOLO SI NO SE HA PREGUNTA ANTES) ---
                out_dir = os.path.join(base_proj, "outputs", manga_name, "MINIATURAS")
                out_path = os.path.join(out_dir, f"MegaRecap_{format_cap(start_c)}_al_{format_cap(end_c)}.png")
                base_detectada = buscar_imagen_base(out_dir)
                
                block_key = f"{manga_name}_{format_cap(start_c)}_{format_cap(end_c)}"
                if not os.path.exists(out_path) and not base_detectada and block_key not in prompted_blocks:
                    print(f"\n[MINIATURA] Configurando miniatura para el Bloque {format_cap(start_c)} al {format_cap(end_c)}")
                    
                    # Intentar obtener el prompt del Short desde la DB
                    _, short_prompt = db_manager.get_short_script(manga_name)
                    
                    # Si no existe, generamos un prompt basado en el resumen general como fallback
                    if not short_prompt:
                        print("  [+] Generando sugerencia de prompt visual de respaldo con Gemini...")
                        import sqlite3
                        summary = None
                        try:
                            conn = sqlite3.connect(db_path)
                            cursor = conn.cursor()
                            clean_name = manga_name.replace("_", "%").replace(" ", "%")
                            cursor.execute("SELECT resumen FROM mangas WHERE titulo LIKE ?", (f"%{clean_name}%",))
                            row = cursor.fetchone()
                            if row:
                                summary = row[0]
                            conn.close()
                        except Exception as e:
                            print(f"  [ERROR DB] {e}")
                        
                        if summary:
                            try:
                                from modules.pipeline.thumbnail_generator import generar_prompt_con_gemini
                                short_prompt = generar_prompt_con_gemini(manga_name.replace("_", " "), summary)
                            except Exception as e:
                                print(f"  [ERROR SUGERENCIA] No se pudo conectar con la IA: {e}")
                    
                    if short_prompt:
                        print("\n" + "="*80)
                        print(">>> PROMPT SUGERIDO PARA TU MINIATURA (BASADO EN EL SHORT / SINOPSIS) <<<")
                        print("="*80)
                        print(short_prompt)
                        print("="*80)
                        print("\n[Instrucciones]:")
                        print("1. Copia el prompt anterior y utilízalo en tu herramienta de IA preferida.")
                        print("2. Descarga la imagen y guárdala en la carpeta MINIATURAS del manga:")
                        print(f"   {out_dir}")
                        print("3. Confirma a continuación si ya la has colocado allí.\n")
                        
                        try:
                            os.makedirs(out_dir, exist_ok=True)
                            confirm = input("¿Has guardado ya la imagen en la carpeta MINIATURAS? (s/n): ").strip().lower()
                            if confirm == 's':
                                base_detectada = buscar_imagen_base(out_dir)
                                if base_detectada:
                                    print(f"\n✅ [OK] ¡Imagen detectada con éxito: {os.path.basename(base_detectada)}! Se procesará con los textos superpuestos más adelante.\n")
                                else:
                                    print("\n[AVISO] No se detectó ninguna imagen en la carpeta. Se continuará con el flujo.")
                            else:
                                print("\n[Omitido] Se continuará. La miniatura se diseñará por defecto con la portada oficial al final.")
                        except Exception as e:
                            print(f"\n[ERROR] Al procesar la confirmación: {e}. Continuando...")
                    
                    prompted_blocks.add(block_key)

                # --- FASE IA: GUIONES Y MINIATURA (Ahorro de Tokens) ---
                print(f"\n>>> [FASE IA] Preparando Bloque: Caps {format_cap(start_c)} al {format_cap(end_c)}")
                
                ia_success = True
                successful_caps = []
                for cap in chunk:
                    pdf_path = os.path.join(pdf_dir, f"Capitulo_{format_cap(cap)}.pdf")
                    if not os.path.exists(pdf_path): pdf_path = os.path.join(pdf_dir, f"{format_cap(cap)}.pdf")
                    mode_sw = "full"
                    
                    if run_pipeline_step(f"Guion Cap {format_cap(cap)}", ["modules/gemini/manga_scriptwriter.py", "--manga", manga_name, "--chapter", format_cap(cap), "--pdf", pdf_path, "--mode", mode_sw]):
                        successful_caps.append(cap)
                    else:
                        print(f"⚠️ Tokens agotados o error en Cap {format_cap(cap)}. Deteniendo Fase IA.")
                        ia_success = False; break
                
                if not ia_success: break # Salir del bucle de IA si falla

                # Metadatos y Miniatura (También IA)
                run_pipeline_step("Metadatos", ["modules/gemini/metadata_generator.py", "--manga", manga_name, "--start", format_cap(start_c), "--end", format_cap(end_c), "--part", str(current_part)])
                if not run_pipeline_step("Miniatura IA", ["modules/gemini/thumbnail_generator.py", "--manga", manga_name, "--start", format_cap(start_c), "--end", format_cap(end_c), "--auto"]):
                    print("⚠️ Falló la miniatura. Deteniendo Fase IA.")
                    break

                if solo_ia:
                    print(f"\n✅ [SOLO IA] Bloque {format_cap(start_c)}-{format_cap(end_c)} finalizado en IA. Pasando al siguiente bloque automáticamente...")
                    cap_offset += cap_limit
                    continue

                # Una vez completada la IA del bloque, marcamos progreso parcial en DB si fuera necesario
                # o simplemente continuamos al siguiente bloque de IA si el usuario quiere "adelantar"
                print(f"✅ Bloque {format_cap(start_c)}-{format_cap(end_c)} listo en IA.")
                
                # --- FASE LOCAL: TRADUCCIÓN, AUDIO Y VIDEO ---
                print(f"\n>>> [FASE LOCAL] Renderizando Bloque: Caps {format_cap(start_c)} al {format_cap(end_c)}")
                
                for cap in successful_caps:
                    run_pipeline_step(f"Traducción Cap {format_cap(cap)}", ["modules/guion_metadatos/script_translator.py", "--manga", manga_name, "--chapter", format_cap(cap)])
                
                for cap in successful_caps:
                    mode_audio = "full"
                    run_pipeline_step(f"Audio Cap {format_cap(cap)}", ["modules/audio/audio_generator.py", "--manga", manga_name, "--chapter", format_cap(cap), "--mode", mode_audio])
                
                for cap in successful_caps:
                    pdf_path = os.path.join(pdf_dir, f"Capitulo_{format_cap(cap)}.pdf")
                    if not os.path.exists(pdf_path): pdf_path = os.path.join(pdf_dir, f"{format_cap(cap)}.pdf")
                    run_pipeline_step(f"Video Cap {format_cap(cap)}", ["modules/video/video_assembler.py", "--manga", manga_name, "--chapter", format_cap(cap), "--pdf", pdf_path, "--mode", "full"])

                run_pipeline_step("Mega Recap", ["modules/video/video_assembler.py", "--manga", manga_name, "--pdf", "none", "--master", "--chapters"] + [format_cap(c) for c in successful_caps])
                run_pipeline_step("Consolidar", ["modules/consolidator.py", "--manga", manga_name, "--start", format_cap(start_c), "--end", format_cap(end_c), "--part", str(current_part)])
                
                # LIMPIEZA
                limpiar_archivos_intermedios(manga_name, chunk)
                
                db_manager.save_pipeline_part(manga_name, current_part, format_cap(start_c), format_cap(end_c))
                print(f"\n[OK] Bloque {format_cap(start_c)}-{format_cap(end_c)} finalizado.")
                
                print(f"\nContinuando automáticamente al siguiente bloque de {cap_limit} capítulos...")
    except ApiKeyExhaustedException as e:
        print(f"\n❌ [GEMINI EXHAUSTED] Deteniendo la producción: {e}")
    except QuotaExceededException as e:
        print(f"\n❌ [CUOTA EXCEDIDA] Deteniendo la producción: {e}")
