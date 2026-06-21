import os
import re
import sys
from dotenv import load_dotenv

# Load env variables from the main project directory
base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(base_proj, '.env'))

from modules.pipeline import db_manager
from modules.flows.common import run_pipeline_step, QuotaExceededException, ApiKeyExhaustedException

def extract_num(fn):
    m = re.search(r'(\d+)', fn)
    return int(m.group(1)) if m else 0

def iniciar_flujo(apagar_al_final=False):
    print("\n" + "="*50)
    print("      --- MODO SHORTS 3.0 ---")
    print("="*50)
    db_manager.init_db()
    
    # Ruta absoluta al proyecto
    base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pdf_base = os.path.join(base_proj, "pdf_storage")
    
    if not os.path.exists(pdf_base):
        print(f"No se encontró la carpeta {pdf_base}.")
        return

    mangas_disponibles = sorted([d for d in os.listdir(pdf_base) if os.path.isdir(os.path.join(pdf_base, d))])
    if not mangas_disponibles:
        print("No hay mangas disponibles en pdf_storage.")
        return

    while True:
        print("\n=== MENÚ MODO SHORTS ===")
        print("1. GENERAR GUION Y METADATOS (NO MINIATURAS)")
        print("2. GENERAR AUDIO Y VIDEO SHORT")
        print("3. SUBIR SHORTS A YOUTUBE (PROGRAMADOR DIARIO - DUPLICADO)")
        print("4. PRODUCCIÓN AUTOMÁTICA COMPLETA (DUPLICADO)")
        print("5. SUBIR SHORTS SIN DUPLICAR (1 subida, alterna 10am/3pm)")
        print("6. PRODUCCIÓN AUTOMÁTICA SIN DUPLICAR (Todo en Uno)")
        print("7. LIMPIAR VIDEOS DUPLICADOS EN YOUTUBE (AUTOMÁTICO)")
        print("8. Volver al menú principal")
        
        opt = input("\nSelecciona una opción: ")
        tarea_realizada = False
        
        if opt == "1":
            iniciar_generacion_guiones(mangas_disponibles, pdf_base)
            tarea_realizada = True
        elif opt == "2":
            iniciar_generacion_videos(mangas_disponibles, pdf_base)
            tarea_realizada = True
        elif opt == "3":
            iniciar_subida_shorts()
            tarea_realizada = True
        elif opt == "4":
            iniciar_produccion_automatica(mangas_disponibles, pdf_base)
            tarea_realizada = True
        elif opt == "5":
            iniciar_subida_shorts_sin_duplicar()
            tarea_realizada = True
        elif opt == "6":
            iniciar_produccion_automatica_sin_duplicar(mangas_disponibles, pdf_base)
            tarea_realizada = True
        elif opt == "7":
            iniciar_limpieza_duplicados()
            tarea_realizada = True
        elif opt == "8":
            break
        else:
            print("Opción no válida.")
            
        if tarea_realizada and apagar_al_final:
            print("\n[APAGADO] Tarea del submenú completada. Volviendo al menú principal para iniciar el apagado...")
            break

def iniciar_generacion_guiones(mangas_disponibles, pdf_base):
    print("\n--- GENERAR GUION Y METADATOS SHORT ---")
    
    mangas_sin_guion = []
    for manga in mangas_disponibles:
        content, _ = db_manager.get_short_script(manga)
        if not content:
            mangas_sin_guion.append(manga)
            
    if not mangas_sin_guion:
        print("No hay mangas pendientes de guión short.")
        return

    print(f"\nMangas sin guión short ({len(mangas_sin_guion)}):")
    for i, m in enumerate(mangas_sin_guion, 1):
        print(f"{i}. {m.replace('_', ' ')}")
    print(f"{len(mangas_sin_guion) + 1}. CREAR TODOS LOS PENDIENTES")
    print(f"{len(mangas_sin_guion) + 2}. Volver")
    
    sel = input("\nSelecciona una opción (número): ")
    if not sel.isdigit():
        return
    idx = int(sel)
    
    if idx == len(mangas_sin_guion) + 2:
        return
    
    to_process = []
    if idx == len(mangas_sin_guion) + 1:
        to_process = mangas_sin_guion
    elif 0 < idx <= len(mangas_sin_guion):
        to_process = [mangas_sin_guion[idx-1]]
    else:
        print("Selección no válida.")
        return

    for manga in to_process:
        pdf_dir = os.path.join(pdf_base, manga)
        pdf_path = os.path.join(pdf_dir, "Capitulo_1.pdf")
        if not os.path.exists(pdf_path):
            pdf_path = os.path.join(pdf_dir, "1.pdf")
        if not os.path.exists(pdf_path):
            all_pdfs = sorted([f for f in os.listdir(pdf_dir) if f.endswith(".pdf")], key=extract_num)
            if all_pdfs:
                pdf_path = os.path.join(pdf_dir, all_pdfs[0])
            else:
                pdf_path = None
        
        if not pdf_path:
            print(f"  [AVISO] No se encontró PDF para {manga}. Saltando...")
            continue
            
        print(f"\n>>> PROCESANDO GUION Y METADATOS SHORT PARA: {manga.replace('_', ' ')}")
        try:
            # 1. Generar guion short en inglés y guardarlo en BD + archivos
            script_ok = run_pipeline_step(
                f"Guion Short {manga}", 
                ["modules/pipeline/manga_scriptwriter.py", "--manga", manga, "--chapter", "1", "--pdf", pdf_path, "--mode", "short"]
            )
            
            if script_ok:
                # 2. Traducir guion short al español
                trans_ok = run_pipeline_step(
                    f"Traducción Short {manga}", 
                    ["modules/pipeline/script_translator.py", "--manga", manga, "--chapter", "1"]
                )
                
                if trans_ok:
                    # 3. Generar metadatos del short (JSON)
                    run_pipeline_step(
                        f"Metadatos Short {manga}", 
                        ["modules/pipeline/metadata_generator.py", "--manga", manga, "--short"]
                    )
                else:
                    print(f"  [AVISO] Falló la traducción para {manga}.")
            else:
                print(f"  [AVISO] Falló la generación de guión short para {manga}.")
        except ApiKeyExhaustedException as e:
            print(f"\n❌ [API KEYS AGOTADAS] Se detiene la generación de guiones short: {e}")
            break

def iniciar_generacion_videos(mangas_disponibles, pdf_base):
    print("\n--- GENERAR AUDIO Y VIDEO SHORT ---")
    
    mangas_sin_video = []
    for manga in mangas_disponibles:
        content, _ = db_manager.get_short_script(manga)
        if content:  # Debe tener guión en base de datos
            if not db_manager.is_short_video_created(manga):
                mangas_sin_video.append(manga)
                
    if not mangas_sin_video:
        print("No hay mangas con guión short que tengan pendiente la creación de su video.")
        return

    print(f"\nMangas con video short pendiente ({len(mangas_sin_video)}):")
    for i, m in enumerate(mangas_sin_video, 1):
        print(f"{i}. {m.replace('_', ' ')}")
    print(f"{len(mangas_sin_video) + 1}. CREAR TODOS LOS VIDEOS PENDIENTES")
    print(f"{len(mangas_sin_video) + 2}. Volver")
    
    sel = input("\nSelecciona una opción (número): ")
    if not sel.isdigit():
        return
    idx = int(sel)
    
    if idx == len(mangas_sin_video) + 2:
        return
    
    to_process = []
    if idx == len(mangas_sin_video) + 1:
        to_process = mangas_sin_video
    elif 0 < idx <= len(mangas_sin_video):
        to_process = [mangas_sin_video[idx-1]]
    else:
        print("Selección no válida.")
        return

    for manga in to_process:
        pdf_dir = os.path.join(pdf_base, manga)
        pdf_path = os.path.join(pdf_dir, "Capitulo_1.pdf")
        if not os.path.exists(pdf_path):
            pdf_path = os.path.join(pdf_dir, "1.pdf")
        if not os.path.exists(pdf_path):
            all_pdfs = sorted([f for f in os.listdir(pdf_dir) if f.endswith(".pdf")], key=extract_num)
            if all_pdfs:
                pdf_path = os.path.join(pdf_dir, all_pdfs[0])
            else:
                pdf_path = None
        
        if not pdf_path:
            print(f"  [AVISO] No se encontró PDF para {manga}. Saltando...")
            continue
            
        print(f"\n>>> GENERANDO MULTIMEDIA SHORT PARA: {manga.replace('_', ' ')}")
        
        # 1. Generar audio para el short
        audio_ok = run_pipeline_step(
            f"Audio Short {manga}",
            ["modules/pipeline/audio_generator.py", "--manga", manga, "--chapter", "1", "--mode", "short"]
        )
        
        if audio_ok:
            # 2. Ensamblar video short
            video_ok = run_pipeline_step(
                f"Video Short {manga}",
                ["modules/pipeline/video_assembler.py", "--manga", manga, "--chapter", "1", "--pdf", pdf_path, "--mode", "short"]
            )
            if video_ok:
                db_manager.mark_short_video_created(manga, 1)
                print(f"  [OK] Short de {manga} registrado como creado en la base de datos.")
            else:
                print(f"  [ERROR] Falló la generación del video para {manga}.")
        else:
            print(f"  [ERROR] Falló la generación del audio para {manga}.")

def calcular_fecha_10am(last_scheduled_str=None):
    import datetime
    target_hour = 10
    target_minute = 0
    
    # Obtener zona horaria local
    tz = datetime.datetime.now().astimezone().tzinfo
    now = datetime.datetime.now(tz)
    
    next_date = None
    if last_scheduled_str:
        try:
            # Parsear la fecha guardada
            last_date = datetime.datetime.fromisoformat(last_scheduled_str)
            # Sumar un dia y forzar las 10:00 AM
            next_date = (last_date + datetime.timedelta(days=1)).replace(
                hour=target_hour, minute=target_minute, second=0, microsecond=0
            )
        except Exception as e:
            print(f"  [YouTube] Error parseando fecha previa '{last_scheduled_str}': {e}. Se reseteara el calendario.")
            next_date = None
            
    if not next_date:
        # Programar hoy a las 10:00 AM en la zona horaria local
        next_date = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        
    # Validar si la fecha calculada esta en el pasado (con margen de 5 minutos)
    if next_date <= now + datetime.timedelta(minutes=5):
        # Si hoy ya paso, programar para mañana a las 10:00 AM
        next_date = (now + datetime.timedelta(days=1)).replace(
            hour=target_hour, minute=target_minute, second=0, microsecond=0
        )
        
    return next_date.isoformat()

def calcular_fecha_3pm(fecha_10am_str):
    import datetime
    # Simplemente parsear la fecha de las 10:00 AM y cambiar la hora a las 15:00 (3 PM)
    dt = datetime.datetime.fromisoformat(fecha_10am_str)
    dt_3pm = dt.replace(hour=15, minute=0, second=0, microsecond=0)
    return dt_3pm.isoformat()

def run_upload_subprocess(command, env):
    import subprocess
    # Ejecuta el uploader y envia la salida a la consola en tiempo real
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
        env=env
    )
    
    full_output = []
    while True:
        line = process.stdout.readline()
        if not line:
            break
        # Limpiar emojis o caracteres no-ASCII para evitar crashes de codificación en Windows
        clean_line = line.encode('ascii', errors='replace').decode('ascii')
        sys.stdout.write(clean_line)
        sys.stdout.flush()
        full_output.append(line)
        
    process.stdout.close()
    process.wait()
    if process.returncode != 0:
        if process.returncode == 42:
            raise QuotaExceededException("Se ha alcanzado la cuota diaria de subidas de videos en YouTube (error 429).")
        raise subprocess.CalledProcessError(process.returncode, command, "".join(full_output))
    return "".join(full_output)

def wait_for_processing(youtube, video_id, check_interval=30):
    import time
    if os.getenv("MOCK_YOUTUBE", "false").lower() == "true":
        print(f"  [MOCK YouTube] Esperando procesamiento del video (ID: {video_id})...")
        print(f"  [MOCK YouTube] [Consulta 1] Estado actual: uploaded. Esperando {check_interval}s...")
        time.sleep(check_interval)
        print(f"  [MOCK YouTube] [Consulta 2] Estado actual: processed.")
        print("  [MOCK YouTube] El video ha sido procesado por completo!")
        return True
        
    print(f"  [YouTube] Esperando procesamiento del video (ID: {video_id})...")
    attempts = 0
    max_attempts = 120  # 60 minutos
    while attempts < max_attempts:
        try:
            request = youtube.videos().list(
                part="status",
                id=video_id
            )
            response = request.execute()
            
            if not response.get("items"):
                print(f"  [YouTube] No se encontro el video con ID {video_id}.")
                return False
                
            status = response["items"][0]["status"]
            upload_status = status.get("uploadStatus")
            
            print(f"  [YouTube] [Consulta {attempts+1}] Estado actual de YouTube: {upload_status}")
            
            if upload_status == "processed":
                print("  [YouTube] El video ha sido procesado por completo!")
                return True
            elif upload_status in ["failed", "rejected"]:
                print(f"  [YouTube] El procesamiento fallo en YouTube. Estado: {upload_status}")
                return False
        except Exception as e:
            print(f"  [YouTube] Error consultando estado: {e}")
            
        attempts += 1
        time.sleep(check_interval)
        
    print("  [YouTube] Se alcanzo el tiempo de espera limite sin completarse el procesamiento.")
    return False

def delete_local_video(file_path):
    if not os.path.exists(file_path):
        print(f"  [Limpieza] El archivo local no existe o ya fue eliminado: {file_path}")
        return False
    try:
        os.remove(file_path)
        print(f"  [Limpieza] Archivo de video local eliminado correctamente: {file_path}")
        return True
    except Exception as e:
        print(f"  [WARNING] [Limpieza] Error al eliminar el archivo local {file_path}: {e}")
        return False

def procesar_subida_manga(manga, base_proj, uploader_path, mock_youtube, yt_client):
    import time
    import re
    import sys
    import sqlite3
    
    print("\n" + "-"*50)
    print(f"Procesando subida del short para: {manga.replace('_', ' ')}")
    
    # Ruta del video local
    video_path = os.path.join(base_proj, "outputs", manga, "VIDEOS", "Short_1.mp4")
    if not os.path.exists(video_path):
        print(f"  [ERROR] El archivo de video local no existe en la ruta:\n   {video_path}")
        return False
        
    # Ruta de los metadatos
    metadata_path = os.path.join(base_proj, "outputs", manga, "Scripts", "short_youtube_data.json")
    if not os.path.exists(metadata_path):
        print(f"  [AVISO] No se encontraron los metadatos en:\n   {metadata_path}")
        return False

    # Consultar base de datos para ver el estado actual de este short
    conn = sqlite3.connect(db_manager.DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT is_uploaded, scheduled_date FROM shorts WHERE manga = ?', (manga.replace(' ', '_'),))
    row = cursor.fetchone()
    conn.close()
    
    is_uploaded = row[0] if row and row[0] is not None else 0
    stored_scheduled_date = row[1] if row else None
    
    if is_uploaded >= 2:
        print(f"  [OK] El short para {manga} ya ha sido subido 2 veces.")
        return True

    # --- PASO 1: SUBIDA 1 (10:00 AM) ---
    if is_uploaded == 0:
        # Calcular fecha programada para las 10:00 AM
        last_date_str = db_manager.get_last_scheduled_short_date()
        scheduled_date_iso_1 = calcular_fecha_10am(last_date_str)
        
        print(f"\n[Subida 1/2] Programando a las 10:00 AM para: {scheduled_date_iso_1}")
        try:
            command = [
                sys.executable, uploader_path, 
                "--video", video_path, 
                "--manga", manga, 
                "--schedule", scheduled_date_iso_1,
                "--json", metadata_path
            ]
            
            env = os.environ.copy()
            env["PYTHONPATH"] = base_proj + os.pathsep + env.get("PYTHONPATH", "")
            
            output_str = run_upload_subprocess(command, env)
            
            youtube_id = None
            if mock_youtube:
                youtube_id = f"mock_yt_1_{int(time.time())}"
            else:
                match = re.search(r'Video subido con ID:\s*([a-zA-Z0-9_-]+)', output_str)
                if match:
                    youtube_id = match.group(1)
                else:
                    match_url = re.search(r'https://youtu\.be/([a-zA-Z0-9_-]+)', output_str)
                    if match_url:
                        youtube_id = match_url.group(1)
                        
            if not youtube_id:
                print("  [ERROR] No se pudo determinar el ID de YouTube de la primera subida.")
                return False
                
            print(f"  [OK] Primera subida exitosa. ID: {youtube_id}")
            
            # Registrar primer paso en la base de datos (is_uploaded se actualiza a 1)
            db_manager.mark_short_as_uploaded_with_date(manga, youtube_id, scheduled_date_iso_1)
            
            # Esperar a que el video sea procesado
            if mock_youtube:
                processed = wait_for_processing(None, youtube_id)
            else:
                processed = wait_for_processing(yt_client, youtube_id)
                
            if not processed:
                print("  [WARNING] [YouTube] El video 1 no se marcó como procesado. Deteniendo el flujo para este manga.")
                return False
                
            is_uploaded = 1
            stored_scheduled_date = scheduled_date_iso_1
            
        except QuotaExceededException:
            raise
        except Exception as e:
            print(f"  [ERROR] Error durante la primera subida de {manga}: {e}")
            return False

    # --- PASO 2: SUBIDA 2 (3:00 PM) ---
    if is_uploaded == 1:
        # Calcular fecha programada para las 3:00 PM (a partir de la fecha de la subida 1)
        scheduled_date_iso_2 = calcular_fecha_3pm(stored_scheduled_date)
        
        print(f"\n[Subida 2/2] Programando a las 3:00 PM para: {scheduled_date_iso_2}")
        try:
            command = [
                sys.executable, uploader_path, 
                "--video", video_path, 
                "--manga", manga, 
                "--schedule", scheduled_date_iso_2,
                "--json", metadata_path
            ]
            
            env = os.environ.copy()
            env["PYTHONPATH"] = base_proj + os.pathsep + env.get("PYTHONPATH", "")
            
            output_str = run_upload_subprocess(command, env)
            
            youtube_id = None
            if mock_youtube:
                youtube_id = f"mock_yt_2_{int(time.time())}"
            else:
                match = re.search(r'Video subido con ID:\s*([a-zA-Z0-9_-]+)', output_str)
                if match:
                    youtube_id = match.group(1)
                else:
                    match_url = re.search(r'https://youtu\.be/([a-zA-Z0-9_-]+)', output_str)
                    if match_url:
                        youtube_id = match_url.group(1)
                        
            if not youtube_id:
                print("  [ERROR] No se pudo determinar el ID de YouTube de la segunda subida.")
                return False
                
            print(f"  [OK] Segunda subida exitosa. ID: {youtube_id}")
            
            # Registrar segundo paso en la base de datos (is_uploaded se actualiza a 2 y concatena IDs)
            db_manager.mark_short_as_uploaded_with_date_step2(manga, youtube_id, scheduled_date_iso_2)
            
            # Esperar a que el video sea procesado
            if mock_youtube:
                processed = wait_for_processing(None, youtube_id)
            else:
                processed = wait_for_processing(yt_client, youtube_id)
                
            if processed:
                delete_local_video(video_path)
                return True
            else:
                print("  [WARNING] [YouTube] El video 2 no se marcó como procesado. No se eliminará el archivo local.")
                return False
                
        except QuotaExceededException:
            raise
        except Exception as e:
            print(f"  [ERROR] Error durante la segunda subida de {manga}: {e}")
            return False

    return False

def iniciar_subida_shorts():
    import time
    print("\n" + "="*50)
    print("      --- SUBIDA Y PROGRAMACION DE SHORTS ---")
    print("="*50)
    
    # Importar sibling api/youtube_uploader
    try:
        base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        parent_dir = os.path.dirname(base_proj)
        if parent_dir not in sys.path:
            sys.path.append(parent_dir)
        from api import youtube_uploader
    except Exception as e:
        print(f"  [ERROR] No se pudo importar el modulo uploader del api: {e}")
        return

    mock_youtube = os.getenv("MOCK_YOUTUBE", "false").lower() == "true"
    
    # 1. Validar credenciales y mostrar canal
    channel_name = None
    try:
        if mock_youtube:
            print("\n[MOCK YouTube] Validando credenciales...")
            time.sleep(1)
            channel_name = os.getenv("MOCK_CHANNEL_NAME", "Canal de Pruebas (Mock)")
            print(f"  [OK] [MOCK YouTube] Credenciales validadas con exito. Canal: {channel_name}\n")
        else:
            print("\n[YouTube] Validando credenciales...")
            yt_client = youtube_uploader.get_authenticated_service()
            if yt_client is None:
                raise ValueError("No se pudo obtener el servicio de YouTube autenticado.")
            channel_name = youtube_uploader.get_channel_info(yt_client)
            print(f"  [OK] [YouTube] Credenciales validadas con exito. Canal: {channel_name}\n")
    except Exception as e:
        print(f"  [ERROR] Autenticacion fallida: {e}")
        return

    # 2. Buscar shorts pendientes de subir
    pending_mangas = db_manager.get_pending_shorts_uploads()
    if not pending_mangas:
        print("No hay shorts pendientes de subida (con video creado y sin subir) en la base de datos.")
        return

    print(f"Se encontraron {len(pending_mangas)} shorts pendientes de subir:")
    for m in pending_mangas:
        print(f" - {m.replace('_', ' ')}")

    confirm = input("\n¿Deseas iniciar la subida y programacion secuencial? (s/n): ").lower()
    if confirm != 's':
        print("Subida cancelada.")
        return

    uploader_path = os.path.join(parent_dir, "api", "youtube_uploader.py")

    try:
        for manga in pending_mangas:
            yt_client_for_manga = None if mock_youtube else yt_client
            procesar_subida_manga(manga, base_proj, uploader_path, mock_youtube, yt_client_for_manga)
    except QuotaExceededException as e:
        print(f"\n❌ [CUOTA EXCEDIDA] Se detiene la subida de shorts restante: {e}")

    print("\n=== PROCESO DE SUBIDA COMPLETADO ===")

def iniciar_produccion_automatica(mangas_disponibles, pdf_base):
    import time
    print("\n" + "="*50)
    print("      --- PRODUCCIÓN AUTOMÁTICA DE SHORTS ---")
    print("="*50)
    
    # 1. Validar e importar uploader de YouTube al principio
    try:
        base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        parent_dir = os.path.dirname(base_proj)
        if parent_dir not in sys.path:
            sys.path.append(parent_dir)
        from api import youtube_uploader
    except Exception as e:
        print(f"  [ERROR] No se pudo importar el modulo uploader del api: {e}")
        return

    mock_youtube = os.getenv("MOCK_YOUTUBE", "false").lower() == "true"
    channel_name = None
    yt_client = None
    try:
        if mock_youtube:
            print("\n[MOCK YouTube] Validando credenciales...")
            time.sleep(1)
            channel_name = os.getenv("MOCK_CHANNEL_NAME", "Canal de Pruebas (Mock)")
            print(f"  [OK] [MOCK YouTube] Credenciales validadas con exito. Canal: {channel_name}\n")
        else:
            print("\n[YouTube] Validando credenciales...")
            yt_client = youtube_uploader.get_authenticated_service()
            if yt_client is None:
                raise ValueError("No se pudo obtener el servicio de YouTube autenticado.")
            channel_name = youtube_uploader.get_channel_info(yt_client)
            print(f"  [OK] [YouTube] Credenciales validadas con exito. Canal: {channel_name}\n")
    except Exception as e:
        print(f"  [ERROR] Autenticacion fallida: {e}")
        return

    # 2. Identificar mangas pendientes (no subidos aún)
    mangas_pendientes = []
    for manga in mangas_disponibles:
        if not db_manager.is_short_uploaded(manga):
            mangas_pendientes.append(manga)

    if not mangas_pendientes:
        print("\nNo hay ningún manga pendiente de producción corta (todos están subidos a YouTube).")
        return

    print(f"\nMangas pendientes de producción ({len(mangas_pendientes)}):")
    for i, m in enumerate(mangas_pendientes, 1):
        print(f" {i}. {m.replace('_', ' ')}")
    print(f"{len(mangas_pendientes) + 1}. PROCESAR TODOS LOS MANGAS PENDIENTES")
    print(f"{len(mangas_pendientes) + 2}. Volver")

    sel = input("\nSelecciona una opción (número): ")
    if not sel.isdigit():
        return
    idx = int(sel)

    if idx == len(mangas_pendientes) + 2:
        return

    to_process = []
    if idx == len(mangas_pendientes) + 1:
        to_process = mangas_pendientes
    elif 0 < idx <= len(mangas_pendientes):
        to_process = [mangas_pendientes[idx-1]]
    else:
        print("Selección no válida.")
        return

    uploader_path = os.path.join(parent_dir, "api", "youtube_uploader.py")

    try:
        for manga in to_process:
            print("\n" + "="*60)
            print(f"[INICIANDO] PIPELINE AUTOMATICO COMPLETO PARA: {manga.replace('_', ' ')}")
            print("="*60)
    
            # Buscar el PDF
            pdf_dir = os.path.join(pdf_base, manga)
            pdf_path = os.path.join(pdf_dir, "Capitulo_1.pdf")
            if not os.path.exists(pdf_path):
                pdf_path = os.path.join(pdf_dir, "1.pdf")
            if not os.path.exists(pdf_path):
                all_pdfs = sorted([f for f in os.listdir(pdf_dir) if f.endswith(".pdf")], key=extract_num)
                if all_pdfs:
                    pdf_path = os.path.join(pdf_dir, all_pdfs[0])
                else:
                    pdf_path = None
            
            if not pdf_path:
                print(f"  [ERROR] No se encontró PDF para {manga}. Saltando...")
                continue
    
            # --- PASO 1: GUION Y METADATOS ---
            content, _ = db_manager.get_short_script(manga)
            script_ok = True
            if not content:
                print(f"\n[PIPELINE - PASO 1] Generando guion y metadatos...")
                script_ok = run_pipeline_step(
                    f"Guion Short {manga}", 
                    ["modules/pipeline/manga_scriptwriter.py", "--manga", manga, "--chapter", "1", "--pdf", pdf_path, "--mode", "short"]
                )
                
                if script_ok:
                    trans_ok = run_pipeline_step(
                        f"Traducción Short {manga}", 
                        ["modules/pipeline/script_translator.py", "--manga", manga, "--chapter", "1"]
                    )
                    if trans_ok:
                        run_pipeline_step(
                            f"Metadatos Short {manga}", 
                            ["modules/pipeline/metadata_generator.py", "--manga", manga, "--short"]
                        )
                    else:
                        print(f"  [ERROR] Falló la traducción para {manga}.")
                        script_ok = False
                else:
                    print(f"  [ERROR] Falló la generación de guión short para {manga}.")
            else:
                print(f"\n[PIPELINE - PASO 1] Guión y metadatos ya existentes en BD. Saltando generación...")
    
            if not script_ok:
                print(f"  [AVISO] No se pudo completar el Paso 1 para {manga}. Saltando al siguiente manga...")
                continue
    
            # --- PASO 2: AUDIO Y VIDEO ---
            video_ok = db_manager.is_short_video_created(manga)
            if not video_ok:
                print(f"\n[PIPELINE - PASO 2] Generando multimedia (audio y video)...")
                audio_ok = run_pipeline_step(
                    f"Audio Short {manga}",
                    ["modules/pipeline/audio_generator.py", "--manga", manga, "--chapter", "1", "--mode", "short"]
                )
                
                if audio_ok:
                    video_ok = run_pipeline_step(
                        f"Video Short {manga}",
                        ["modules/pipeline/video_assembler.py", "--manga", manga, "--chapter", "1", "--pdf", pdf_path, "--mode", "short"]
                    )
                    if video_ok:
                        db_manager.mark_short_video_created(manga, 1)
                        print(f"  [OK] Short de {manga} registrado como creado en la base de datos.")
                    else:
                        print(f"  [ERROR] Falló la generación del video para {manga}.")
                else:
                    print(f"  [ERROR] Falló la generación del audio para {manga}.")
            else:
                print(f"\n[PIPELINE - PASO 2] Video local ya creado anteriormente. Saltando generación...")
    
            if not video_ok:
                print(f"  [AVISO] No se pudo completar el Paso 2 para {manga}. Saltando al siguiente manga...")
                continue
    
            # --- PASO 3: SUBIDA Y PROGRAMACIÓN ---
            print(f"\n[PIPELINE - PASO 3] Subiendo y programando short en YouTube...")
            yt_client_for_manga = None if mock_youtube else yt_client
            subida_ok = procesar_subida_manga(manga, base_proj, uploader_path, mock_youtube, yt_client_for_manga)
            if not subida_ok:
                print(f"  [AVISO] No se pudo completar el Paso 3 para {manga}. Saltando al siguiente manga...")
                continue
    except QuotaExceededException as e:
        print(f"\n❌ [CUOTA EXCEDIDA] Se detiene la producción automática de shorts: {e}")
    except ApiKeyExhaustedException as e:
        print(f"\n❌ [API KEYS AGOTADAS] Se detiene la producción automática de shorts: {e}")

    print("\n=== PIPELINE DE PRODUCCIÓN AUTOMÁTICA FINALIZADO ===")

def calcular_siguiente_slot(last_scheduled_str=None):
    import datetime
    tz = datetime.datetime.now().astimezone().tzinfo
    now = datetime.datetime.now(tz)
    
    next_date = None
    if last_scheduled_str:
        try:
            last_date = datetime.datetime.fromisoformat(last_scheduled_str)
            if last_date.hour < 12:
                next_date = last_date.replace(hour=15, minute=0, second=0, microsecond=0)
            else:
                next_date = (last_date + datetime.timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        except Exception as e:
            print(f"  [YouTube] Error parseando fecha previa '{last_scheduled_str}': {e}. Se reseteará el calendario.")
            next_date = None
            
    if not next_date:
        next_date = now.replace(hour=10, minute=0, second=0, microsecond=0)
        
    while next_date <= now + datetime.timedelta(minutes=5):
        if next_date.hour < 12:
            next_date = next_date.replace(hour=15, minute=0, second=0, microsecond=0)
        else:
            next_date = (next_date + datetime.timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
            
    return next_date.isoformat()

def procesar_subida_manga_sin_duplicar(manga, base_proj, uploader_path, mock_youtube, yt_client):
    import time
    import re
    import sys
    import sqlite3
    import datetime
    
    print("\n" + "-"*50)
    print(f"Procesando subida única (Sin Duplicar) para: {manga.replace('_', ' ')}")
    
    video_path = os.path.join(base_proj, "outputs", manga, "VIDEOS", "Short_1.mp4")
    if not os.path.exists(video_path):
        print(f"  [ERROR] El archivo de video local no existe en la ruta:\n   {video_path}")
        return False
        
    metadata_path = os.path.join(base_proj, "outputs", manga, "Scripts", "short_youtube_data.json")
    if not os.path.exists(metadata_path):
        print(f"  [AVISO] No se encontraron los metadatos en:\n   {metadata_path}")
        return False

    conn = sqlite3.connect(db_manager.DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT is_uploaded FROM shorts WHERE manga = ?', (manga.replace(' ', '_'),))
    row = cursor.fetchone()
    conn.close()
    
    is_uploaded = row[0] if row and row[0] is not None else 0
    
    if is_uploaded >= 2:
        print(f"  [OK] El short para {manga} ya está marcado como completamente subido (is_uploaded={is_uploaded}).")
        return True

    last_date_str = db_manager.get_last_scheduled_short_date()
    next_slot_iso = calcular_siguiente_slot(last_date_str)
    
    try:
        dt = datetime.datetime.fromisoformat(next_slot_iso)
        hora_desc = "10:00 AM" if dt.hour < 12 else "3:00 PM"
    except Exception:
        hora_desc = "10:00 AM"
        
    print(f"\n[Subida Única] Programando a las {hora_desc} para: {next_slot_iso}")
    try:
        command = [
            sys.executable, uploader_path, 
            "--video", video_path, 
            "--manga", manga, 
            "--schedule", next_slot_iso,
            "--json", metadata_path
        ]
        
        env = os.environ.copy()
        env["PYTHONPATH"] = base_proj + os.pathsep + env.get("PYTHONPATH", "")
        
        output_str = run_upload_subprocess(command, env)
        
        youtube_id = None
        if mock_youtube:
            youtube_id = f"mock_yt_single_{int(time.time())}"
        else:
            match = re.search(r'Video subido con ID:\s*([a-zA-Z0-9_-]+)', output_str)
            if match:
                youtube_id = match.group(1)
            else:
                match_url = re.search(r'https://youtu\.be/([a-zA-Z0-9_-]+)', output_str)
                if match_url:
                    youtube_id = match_url.group(1)
                    
        if not youtube_id:
            print("  [ERROR] No se pudo determinar el ID de YouTube de la subida.")
            return False
            
        print(f"  [OK] Subida exitosa. ID: {youtube_id}")
        
        db_manager.mark_short_as_uploaded_single(manga, youtube_id, next_slot_iso)
        
        if mock_youtube:
            processed = wait_for_processing(None, youtube_id)
        else:
            processed = wait_for_processing(yt_client, youtube_id)
            
        if processed:
            delete_local_video(video_path)
            return True
        else:
            print("  [WARNING] [YouTube] El video no se marcó como procesado. No se eliminará el archivo local.")
            return False
            
    except QuotaExceededException:
        raise
    except Exception as e:
        print(f"  [ERROR] Error durante la subida sin duplicar de {manga}: {e}")
        return False

def iniciar_subida_shorts_sin_duplicar():
    import time
    print("\n" + "="*50)
    print("   --- SUBIDA DE SHORTS SIN DUPLICAR (1 SUBIDA) ---")
    print("="*50)
    
    try:
        base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        parent_dir = os.path.dirname(base_proj)
        if parent_dir not in sys.path:
            sys.path.append(parent_dir)
        from api import youtube_uploader
    except Exception as e:
        print(f"  [ERROR] No se pudo importar el modulo uploader del api: {e}")
        return

    mock_youtube = os.getenv("MOCK_YOUTUBE", "false").lower() == "true"
    
    channel_name = None
    try:
        if mock_youtube:
            print("\n[MOCK YouTube] Validando credenciales...")
            time.sleep(1)
            channel_name = os.getenv("MOCK_CHANNEL_NAME", "Canal de Pruebas (Mock)")
            print(f"  [OK] [MOCK YouTube] Credenciales validadas con exito. Canal: {channel_name}\n")
        else:
            print("\n[YouTube] Validando credenciales...")
            yt_client = youtube_uploader.get_authenticated_service()
            if yt_client is None:
                raise ValueError("No se pudo obtener el servicio de YouTube autenticado.")
            channel_name = youtube_uploader.get_channel_info(yt_client)
            print(f"  [OK] [YouTube] Credenciales validadas con exito. Canal: {channel_name}\n")
    except Exception as e:
        print(f"  [ERROR] Autenticacion fallida: {e}")
        return

    pending_mangas = db_manager.get_pending_shorts_uploads()
    if not pending_mangas:
        print("No hay shorts pendientes de subida (con video creado y sin subir) en la base de datos.")
        return

    print(f"Se encontraron {len(pending_mangas)} shorts pendientes de subir (Sin Duplicar):")
    for m in pending_mangas:
        print(f" - {m.replace('_', ' ')}")

    confirm = input("\n¿Deseas iniciar la subida secuencial sin duplicados? (s/n): ").lower()
    if confirm != 's':
        print("Subida cancelada.")
        return

    uploader_path = os.path.join(parent_dir, "api", "youtube_uploader.py")

    try:
        for manga in pending_mangas:
            yt_client_for_manga = None if mock_youtube else yt_client
            procesar_subida_manga_sin_duplicar(manga, base_proj, uploader_path, mock_youtube, yt_client_for_manga)
    except QuotaExceededException as e:
        print(f"\n❌ [CUOTA EXCEDIDA] Se detiene la subida de shorts restante: {e}")

    print("\n=== PROCESO DE SUBIDA COMPLETADO ===")

def iniciar_produccion_automatica_sin_duplicar(mangas_disponibles, pdf_base):
    import time
    print("\n" + "="*50)
    print("   --- PRODUCCIÓN AUTOMÁTICA DE SHORTS SIN DUPLICAR ---")
    print("="*50)
    
    try:
        base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        parent_dir = os.path.dirname(base_proj)
        if parent_dir not in sys.path:
            sys.path.append(parent_dir)
        from api import youtube_uploader
    except Exception as e:
        print(f"  [ERROR] No se pudo importar el modulo uploader del api: {e}")
        return

    mock_youtube = os.getenv("MOCK_YOUTUBE", "false").lower() == "true"
    channel_name = None
    yt_client = None
    try:
        if mock_youtube:
            print("\n[MOCK YouTube] Validando credenciales...")
            time.sleep(1)
            channel_name = os.getenv("MOCK_CHANNEL_NAME", "Canal de Pruebas (Mock)")
            print(f"  [OK] [MOCK YouTube] Credenciales validadas con exito. Canal: {channel_name}\n")
        else:
            print("\n[YouTube] Validando credenciales...")
            yt_client = youtube_uploader.get_authenticated_service()
            if yt_client is None:
                raise ValueError("No se pudo obtener el servicio de YouTube autenticado.")
            channel_name = youtube_uploader.get_channel_info(yt_client)
            print(f"  [OK] [YouTube] Credenciales validadas con exito. Canal: {channel_name}\n")
    except Exception as e:
        print(f"  [ERROR] Autenticacion fallida: {e}")
        return

    mangas_pendientes = []
    for manga in mangas_disponibles:
        if not db_manager.is_short_uploaded(manga):
            mangas_pendientes.append(manga)

    if not mangas_pendientes:
        print("\nNo hay ningún manga pendiente de producción corta.")
        return

    print(f"\nMangas pendientes de producción ({len(mangas_pendientes)}):")
    for i, m in enumerate(mangas_pendientes, 1):
        print(f" {i}. {m.replace('_', ' ')}")
    print(f"{len(mangas_pendientes) + 1}. PROCESAR TODOS LOS MANGAS PENDIENTES")
    print(f"{len(mangas_pendientes) + 2}. Volver")

    sel = input("\nSelecciona una opción (número): ")
    if not sel.isdigit():
        return
    idx = int(sel)

    if idx == len(mangas_pendientes) + 2:
        return

    to_process = []
    if idx == len(mangas_pendientes) + 1:
        to_process = mangas_pendientes
    elif 0 < idx <= len(mangas_pendientes):
        to_process = [mangas_pendientes[idx-1]]
    else:
        print("Selección no válida.")
        return

    uploader_path = os.path.join(parent_dir, "api", "youtube_uploader.py")

    try:
        for manga in to_process:
            print("\n" + "="*60)
            print(f"[INICIANDO] PIPELINE COMPLETO SIN DUPLICAR PARA: {manga.replace('_', ' ')}")
            print("="*60)
    
            pdf_dir = os.path.join(pdf_base, manga)
            pdf_path = os.path.join(pdf_dir, "Capitulo_1.pdf")
            if not os.path.exists(pdf_path):
                pdf_path = os.path.join(pdf_dir, "1.pdf")
            if not os.path.exists(pdf_path):
                all_pdfs = sorted([f for f in os.listdir(pdf_dir) if f.endswith(".pdf")], key=extract_num)
                if all_pdfs:
                    pdf_path = os.path.join(pdf_dir, all_pdfs[0])
                else:
                    pdf_path = None
            
            if not pdf_path:
                print(f"  [ERROR] No se encontró PDF para {manga}. Saltando...")
                continue
    
            content, _ = db_manager.get_short_script(manga)
            script_ok = True
            if not content:
                print(f"\n[PIPELINE - PASO 1] Generando guion y metadatos...")
                script_ok = run_pipeline_step(
                    f"Guion Short {manga}", 
                    ["modules/pipeline/manga_scriptwriter.py", "--manga", manga, "--chapter", "1", "--pdf", pdf_path, "--mode", "short"]
                )
                
                if script_ok:
                    trans_ok = run_pipeline_step(
                        f"Traducción Short {manga}", 
                        ["modules/pipeline/script_translator.py", "--manga", manga, "--chapter", "1"]
                    )
                    if trans_ok:
                        run_pipeline_step(
                            f"Metadatos Short {manga}", 
                            ["modules/pipeline/metadata_generator.py", "--manga", manga, "--short"]
                        )
                    else:
                        print(f"  [ERROR] Falló la traducción para {manga}.")
                        script_ok = False
                else:
                    print(f"  [ERROR] Falló la generación de guión short para {manga}.")
            else:
                print(f"\n[PIPELINE - PASO 1] Guión y metadatos ya existentes en BD. Saltando...")
    
            if not script_ok:
                print(f"  [AVISO] No se pudo completar el Paso 1 para {manga}. Saltando...")
                continue
    
            video_ok = db_manager.is_short_video_created(manga)
            if not video_ok:
                print(f"\n[PIPELINE - PASO 2] Generando multimedia...")
                audio_ok = run_pipeline_step(
                    f"Audio Short {manga}",
                    ["modules/pipeline/audio_generator.py", "--manga", manga, "--chapter", "1", "--mode", "short"]
                )
                
                if audio_ok:
                    video_ok = run_pipeline_step(
                        f"Video Short {manga}",
                        ["modules/pipeline/video_assembler.py", "--manga", manga, "--chapter", "1", "--pdf", pdf_path, "--mode", "short"]
                    )
                    if video_ok:
                        db_manager.mark_short_video_created(manga, 1)
                        print(f"  [OK] Short de {manga} registrado como creado en la base de datos.")
                    else:
                        print(f"  [ERROR] Falló la generación del video para {manga}.")
                else:
                    print(f"  [ERROR] Falló la generación del audio para {manga}.")
            else:
                print(f"\n[PIPELINE - PASO 2] Video local ya creado. Saltando...")
    
            if not video_ok:
                print(f"  [AVISO] No se pudo completar el Paso 2 para {manga}. Saltando...")
                continue
    
            print(f"\n[PIPELINE - PASO 3] Subiendo y programando short sin duplicar...")
            yt_client_for_manga = None if mock_youtube else yt_client
            subida_ok = procesar_subida_manga_sin_duplicar(manga, base_proj, uploader_path, mock_youtube, yt_client_for_manga)
            if not subida_ok:
                print(f"  [AVISO] No se pudo completar el Paso 3 para {manga}. Saltando...")
                continue
    except QuotaExceededException as e:
        print(f"\n❌ [CUOTA EXCEDIDA] Se detiene la producción automática de shorts: {e}")
    except ApiKeyExhaustedException as e:
        print(f"\n❌ [API KEYS AGOTADAS] Se detiene la producción automática de shorts: {e}")
 
    print("\n=== PIPELINE DE PRODUCCIÓN AUTOMÁTICA FINALIZADO ===")

def iniciar_limpieza_duplicados():
    print("\n" + "="*50)
    print("   --- INICIANDO LIMPIEZA AUTOMÁTICA DE DUPLICADOS ---")
    print("="*50)
    
    try:
        base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        parent_dir = os.path.dirname(base_proj)
        api_dir = os.path.join(parent_dir, "api")
        if api_dir not in sys.path:
            sys.path.append(api_dir)
        import delete_youtube_duplicates
        
        import importlib
        importlib.reload(delete_youtube_duplicates)
        delete_youtube_duplicates.main()
    except Exception as e:
        print(f"  [ERROR] Ocurrió un error al ejecutar la limpieza: {e}")
    
    print("\n=== PROCESO DE LIMPIEZA COMPLETADO ===")
