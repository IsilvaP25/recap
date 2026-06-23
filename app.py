import os
import sys
import threading
import shutil
import time
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS

# Asegurarnos de que puede importar los modulos locales
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules import database, token_monitor, pdf_converter, comments_manager
from modules import db_manager
from modules.flows import downloader_flow, production_flow, autopilot_flow
from modules.api_config import obtener_capitulos_por_parte

import queue

_download_queue = queue.Queue()
_current_download = None
_queue_lock = threading.Lock()

def _download_worker():
    global _current_download
    while True:
        task = _download_queue.get()
        if task is None:
            break
        
        with _queue_lock:
            _current_download = task.get("title")
            
        print(f"\n[COLA] Iniciando descarga de: {_current_download}...")
        try:
            task_func = task.get("func")
            task_func()
        except Exception as e:
            print(f"\n[COLA] [ERROR] Error descargando {_current_download}: {e}")
        finally:
            with _queue_lock:
                _current_download = None
            _download_queue.task_done()
            print(f"[COLA] Finalizada la tarea. Buscando siguiente en cola...")

# Iniciar el hilo trabajador
_worker_thread = threading.Thread(target=_download_worker, daemon=True)
_worker_thread.start()

app = Flask(__name__)
CORS(app)

_global_logs = []
_logs_lock = threading.Lock()

class LogCaptureStream:
    def __init__(self, original_stream):
        self.original_stream = original_stream

    def write(self, text):
        self.original_stream.write(text)
        if text:
            # Skip Werkzeug logging of the logs, images, static, and outputs endpoints to prevent infinite polling log loops
            if "GET /api/logs" in text or "GET /images" in text or "GET /outputs" in text or "GET /static" in text:
                return
            with _logs_lock:
                _global_logs.append(text)
                if len(_global_logs) > 2000:
                    del _global_logs[:-1000]

    def flush(self):
        self.original_stream.flush()

# Redirect stdout and stderr
sys.stdout = LogCaptureStream(sys.stdout)
sys.stderr = LogCaptureStream(sys.stderr)

# Configuración de carpetas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_FOLDER = os.path.join(BASE_DIR, 'raw_downloads')
TRASH_FOLDER = os.path.join(IMAGE_FOLDER, '.trash')

deleted_history = [] # Pila para guardar historial de borrados

@app.route('/')
def index():
    return render_template('index.html')

def run_flow_in_background(flow_func):
    thread = threading.Thread(target=flow_func)
    thread.daemon = True
    thread.start()

@app.route('/api/run_flow', methods=['POST'])
def run_flow():
    data = request.json
    flow_id = data.get('flow_id')

    if flow_id == '1':
        run_flow_in_background(downloader_flow.iniciar_flujo)
        return jsonify({"status": "success", "message": "Iniciando descarga de manga..."})
    elif flow_id == '3':
        run_flow_in_background(production_flow.iniciar_flujo)
        return jsonify({"status": "success", "message": "Iniciando motor de producción..."})
    elif flow_id == '4':
        run_flow_in_background(autopilot_flow.iniciar_flujo)
        return jsonify({"status": "success", "message": "Iniciando producción automática..."})
    elif flow_id == '5':
        token_monitor.consultar_cuota_actual()
        token_monitor.validar_acceso_gemini()
        return jsonify({"status": "success", "message": "Revisando cuotas en la consola"})
    
    return jsonify({"status": "error", "message": "Flujo no válido"}), 400

@app.route('/api/search_manga', methods=['GET'])
def api_search_manga():
    query = request.args.get('query', '')
    if not query:
        return jsonify([])
    from modules import manga_search
    resultados = manga_search.buscar_por_titulo(query)
    return jsonify(resultados)

@app.route('/api/genres', methods=['GET'])
def api_genres():
    from modules import manga_search
    return jsonify(manga_search.GENRES)

@app.route('/api/search_genre_year', methods=['GET'])
def api_search_genre_year():
    genre = request.args.get('genre', '')
    year_str = request.args.get('year', '')
    if not genre or not year_str:
        return jsonify([])
    try:
        year_min = int(year_str)
    except ValueError:
        return jsonify([])
    from modules import manga_search
    resultados = manga_search.buscar_por_genero_y_ano(genre, year_min, limit=30, max_pages=15)
    return jsonify(resultados)

@app.route('/api/download_manga', methods=['POST'])
def api_download_manga():
    data = request.json
    m_id = data.get('manga_id')
    m_titulo = data.get('manga_title')
    manga_data = data.get('manga_data')
    
    if not m_id or not m_titulo:
        return jsonify({"status": "error", "message": "Datos insuficientes"}), 400
        
    def download_task():
        downloader_flow.ejecutar_descarga_manga(m_id, m_titulo, automatico=True, manga_data=manga_data)
        
    # Encolar la tarea
    task = {
        "title": m_titulo,
        "func": download_task
    }
    _download_queue.put(task)
    
    pos = _download_queue.qsize()
    if pos > 0 and _current_download is not None:
        message = f"Descarga de '{m_titulo}' añadida a la cola (Posición en espera: {pos})."
    else:
        message = f"Iniciando descarga de '{m_titulo}' inmediatamente..."
        
    return jsonify({"status": "success", "message": message})

# --- NUEVOS ENDPOINTS PARA NAVEGACIÓN Y CONVERSIÓN A PDF ---


@app.route('/api/mangas', methods=['GET'])
def get_mangas():
    """Retorna la lista de mangas (carpetas en raw_downloads)"""
    if not os.path.exists(IMAGE_FOLDER):
        return jsonify([])
    mangas = [d for d in os.listdir(IMAGE_FOLDER) if os.path.isdir(os.path.join(IMAGE_FOLDER, d))]
    return jsonify(mangas)

@app.route('/api/mangas/<manga_name>/chapters', methods=['GET'])
def get_chapters(manga_name):
    """Retorna los capítulos de un manga específico"""
    manga_path = os.path.join(IMAGE_FOLDER, manga_name)
    if not os.path.exists(manga_path):
        return jsonify([])
    
    # Importar función de sort de pdf_converter para orden natural
    from modules.pdf_converter import get_natural_key
    chapters = [d for d in os.listdir(manga_path) if os.path.isdir(os.path.join(manga_path, d))]
    chapters.sort(key=get_natural_key)
    return jsonify(chapters)

@app.route('/api/mangas/<manga_name>/chapters/<chapter_name>/images', methods=['GET'])
def get_images(manga_name, chapter_name):
    """Retorna las imágenes de un capítulo específico"""
    cap_path = os.path.join(IMAGE_FOLDER, manga_name, chapter_name)
    if not os.path.exists(cap_path):
        return jsonify([])
    
    from modules.pdf_converter import get_natural_key
    images = [f for f in os.listdir(cap_path) if f.lower().endswith(('.webp', '.png', '.jpg', '.jpeg'))]
    images.sort(key=get_natural_key)
    
    # Generar array con información
    img_data = []
    for img in images:
        rel_path = f"{manga_name}/{chapter_name}/{img}"
        img_data.append({
            "name": img,
            "path": rel_path
        })
    return jsonify(img_data)

@app.route('/api/convert_pdf', methods=['POST'])
def convert_pdf():
    """Convierte los capítulos seleccionados a PDF sin bloquear la consola"""
    data = request.json
    manga_name = data.get('manga_name')
    chapters = data.get('chapters') # Lista de capítulos o 'all'
    
    if not manga_name:
        return jsonify({"status": "error", "message": "Manga no especificado"}), 400
        
    def pdf_task():
        if chapters == 'all':
            print(f"Iniciando conversión de TODOS los capítulos para {manga_name}")
            pdf_converter.convert_webp_to_pdf(manga_name)
        else:
            print(f"Iniciando conversión de {len(chapters)} capítulos para {manga_name}")
            pdf_converter.convert_webp_to_pdf(manga_name, chapters_to_process=chapters)
        print("✅ Conversión PDF finalizada.")

    run_flow_in_background(pdf_task)
    return jsonify({"status": "success", "message": f"Iniciando conversión a PDF para {manga_name}..."})


@app.route('/api/library', methods=['GET'])
def get_library():
    try:
        from modules.utils import sanitizar_nombre_carpeta
        import sqlite3
        conn = database.conectar()
        cursor = conn.cursor()
        cursor.execute('SELECT id, titulo, resumen, total_capitulos, estado, tipo FROM mangas')
        rows = cursor.fetchall()
        
        library_data = []
        for m_id, titulo, resumen, total_caps, estado, tipo in rows:
            folder_name = sanitizar_nombre_carpeta(titulo)
            
            # Count downloaded chapters
            cursor.execute('SELECT COUNT(*) FROM capitulos WHERE manga_id = ? AND descargado = 1', (m_id,))
            downloaded_count = cursor.fetchone()[0]
            
            # Check if cover exists
            cover_url = None
            cover_dir = os.path.join(BASE_DIR, "outputs", folder_name, "COVER")
            if os.path.exists(cover_dir):
                for f in os.listdir(cover_dir):
                    if f.startswith("official_cover."):
                        cover_url = f"/outputs/{folder_name}/COVER/{f}"
                        break
            
            library_data.append({
                "id": m_id,
                "title": titulo,
                "summary": resumen,
                "total_chapters": total_caps or 0,
                "downloaded_count": downloaded_count,
                "status": estado or "unknown",
                "type": tipo or "manga",
                "folder_name": folder_name,
                "cover_url": cover_url
            })
        conn.close()
        return jsonify(library_data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/mangas/download_remaining', methods=['POST'])
def api_download_remaining():
    data = request.json
    m_id = data.get('manga_id')
    m_title = data.get('manga_title')
    
    if not m_id or not m_title:
        return jsonify({"status": "error", "message": "Datos insuficientes"}), 400
        
    def download_task():
        print(f"Iniciando descarga de capítulos restantes para: {m_title}")
        downloader_flow.ejecutar_descarga_manga(m_id, m_title, automatico=True)
        print(f"Descarga de capítulos restantes para {m_title} completada.")
        
    # Encolar la tarea
    task = {
        "title": m_title,
        "func": download_task
    }
    _download_queue.put(task)
    
    pos = _download_queue.qsize()
    if pos > 0 and _current_download is not None:
        message = f"Descarga de restantes de '{m_title}' añadida a la cola (Posición en espera: {pos})."
    else:
        message = f"Iniciando descarga de restantes de '{m_title}' inmediatamente..."
        
    return jsonify({"status": "success", "message": message})

@app.route('/api/download_queue/status', methods=['GET'])
def api_get_download_queue_status():
    try:
        return jsonify({
            "current": _current_download,
            "queue_size": _download_queue.qsize()
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/mangas/delete', methods=['POST'])
def api_delete_manga():
    data = request.json
    m_id = data.get('manga_id')
    m_title = data.get('manga_title')
    
    if not m_id:
        return jsonify({"status": "error", "message": "Falta el ID del manga"}), 400
        
    try:
        conn = database.conectar()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM guiones WHERE chapter_id IN (SELECT id FROM capitulos WHERE manga_id = ?)', (m_id,))
        cursor.execute('DELETE FROM imagenes WHERE chapter_id IN (SELECT id FROM capitulos WHERE manga_id = ?)', (m_id,))
        cursor.execute('DELETE FROM capitulos WHERE manga_id = ?', (m_id,))
        cursor.execute('DELETE FROM mangas WHERE id = ?', (m_id,))
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success", "message": f"'{m_title}' eliminado de la base de datos con éxito."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/logs', methods=['GET'])
def get_logs():
    start = int(request.args.get('start', 0))
    with _logs_lock:
        if start < 0 or start > len(_global_logs):
            return jsonify({
                "logs": _global_logs,
                "next_start": len(_global_logs)
            })
        return jsonify({
            "logs": _global_logs[start:],
            "next_start": len(_global_logs)
        })


# --- ENDPOINTS PARA COMENTARIOS DE YOUTUBE ---

@app.route('/api/comments/sync', methods=['POST'])
def api_sync_comments():
    try:
        res = comments_manager.sincronizar_comentarios_canal()
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/comments', methods=['GET'])
def api_get_comments():
    try:
        comments = database.obtener_comentarios_pendientes()
        enriched_comments = []
        for c in comments:
            manga_key = c['manga_key']
            manga_id = database.obtener_manga_por_titulo_sanitizado(manga_key)
            
            manga_info = None
            if manga_id:
                m_row = database.obtener_manga(manga_id)
                if m_row:
                    conn = database.conectar()
                    cursor = conn.cursor()
                    cursor.execute('SELECT COUNT(*) FROM capitulos WHERE manga_id = ? AND descargado = 1', (manga_id,))
                    downloaded = cursor.fetchone()[0]
                    conn.close()
                    
                    cover_url = None
                    cover_dir = os.path.join(BASE_DIR, "outputs", manga_key, "COVER")
                    if os.path.exists(cover_dir):
                        for f in os.listdir(cover_dir):
                            if f.startswith("official_cover."):
                                cover_url = f"/outputs/{manga_key}/COVER/{f}"
                                break
                                
                    manga_info = {
                        "id": m_row[0],
                        "title": m_row[1],
                        "summary": m_row[2],
                        "total_chapters": m_row[3] or 0,
                        "downloaded_count": downloaded,
                        "status": m_row[4] or "unknown",
                        "type": m_row[5] or "manga",
                        "cover_url": cover_url
                    }
            
            c['manga_info'] = manga_info
            
            video_path = os.path.join(BASE_DIR, "outputs", manga_key, "VIDEOS", "Short_1.mp4")
            c['local_video_exists'] = os.path.exists(video_path)
            c['local_video_url'] = f"/outputs/{manga_key}/VIDEOS/Short_1.mp4" if c['local_video_exists'] else None
            
            enriched_comments.append(c)
            
        return jsonify(enriched_comments)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/comments/<comment_id>/read', methods=['POST'])
def api_mark_comment_read(comment_id):
    try:
        database.marcar_comentario_leido(comment_id)
        return jsonify({"status": "success", "message": "Comentario marcado como leído."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/comments/count', methods=['GET'])
def api_get_comments_count():
    try:
        count = database.obtener_cantidad_comentarios_sin_leer()
        return jsonify({"count": count})
    except Exception as e:
        return jsonify({"count": 0, "error": str(e)})


# --- ENDPOINTS PARA PREVISUALIZAR Y BORRAR SPAM ---

@app.route('/outputs/<path:filename>')
def serve_output(filename):
    """Sirve archivos desde la carpeta de outputs (ej: miniaturas, metadatos)"""
    outputs_folder = os.path.join(BASE_DIR, 'outputs')
    return send_from_directory(outputs_folder, filename)

@app.route('/api/mangas/<manga_name>/next_block_preview', methods=['GET'])
def get_next_block_preview(manga_name):
    """Obtiene la previsualización de metadatos y miniatura del siguiente bloque largo"""
    import json
    import re
    
    # 1. Obtener última parte y capítulo desde la DB
    last_part, last_cap_done = db_manager.get_last_part(manga_name)
    next_part = last_part + 1
    start_chapter = last_cap_done + 1
    
    # 2. Calcular capítulos disponibles en pdf_storage para este manga
    pdf_dir = os.path.join(BASE_DIR, "pdf_storage", manga_name)
    avail_caps = []
    if os.path.exists(pdf_dir):
        all_pdfs = sorted([f for f in os.listdir(pdf_dir) if f.endswith(".pdf")])
        for f in all_pdfs:
            m = re.search(r'(\d+)', f)
            if m:
                avail_caps.append(int(m.group(1)))
    avail_caps = sorted(list(set(avail_caps)))
    
    # Filtrar solo a partir del siguiente capítulo
    avail_caps_for_block = [c for c in avail_caps if c >= start_chapter]
    cap_limit = obtener_capitulos_por_parte()
    if avail_caps_for_block:
        block_caps = avail_caps_for_block[:cap_limit]
        expected_end = block_caps[-1]
    else:
        expected_end = start_chapter + (cap_limit - 1)
        
    # 3. Buscar el archivo de metadatos
    meta_path = os.path.join(BASE_DIR, "outputs", manga_name, "Scripts", f"Capitulo_{start_chapter}_metadata.json")
    
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta_data = json.load(f)
        except Exception as e:
            meta_data = None
            
        if meta_data:
            title = meta_data.get("clickbait_title", "")
            description = meta_data.get("description", "")
            thumbnail_prompt = meta_data.get("thumbnail_prompt", "")
            chapter_range = meta_data.get("chapter_range", "")
            
            end_chapter = expected_end
            if chapter_range and '-' in chapter_range:
                try:
                    end_chapter = int(chapter_range.split('-')[1])
                except ValueError:
                    pass
            
            # Buscar la miniatura
            thumb_relative_path = None
            thumb_dir = os.path.join(BASE_DIR, "outputs", manga_name, "MINIATURAS")
            if os.path.exists(thumb_dir):
                for filename in os.listdir(thumb_dir):
                    if filename.startswith(f"MegaRecap_{start_chapter}_al_") and filename.endswith(".png"):
                        thumb_relative_path = f"{manga_name}/MINIATURAS/{filename}"
                        break
            
            if not thumb_relative_path:
                default_thumb = os.path.join(BASE_DIR, "outputs", manga_name, "MINIATURAS", f"MegaRecap_{start_chapter}_al_{end_chapter}.png")
                if os.path.exists(default_thumb):
                    thumb_relative_path = f"{manga_name}/MINIATURAS/MegaRecap_{start_chapter}_al_{end_chapter}.png"
                else:
                    pub_dir = os.path.join(BASE_DIR, "outputs", manga_name, "FINAL_PUBLICATION", f"Recap_Parte_{next_part}_Caps_{start_chapter}_al_{end_chapter}")
                    if os.path.exists(os.path.join(pub_dir, "thumbnail.png")):
                        thumb_relative_path = f"{manga_name}/FINAL_PUBLICATION/Recap_Parte_{next_part}_Caps_{start_chapter}_al_{end_chapter}/thumbnail.png"
            
            thumbnail_url = f"/outputs/{thumb_relative_path.replace(os.sep, '/')}" if thumb_relative_path else None
            
            return jsonify({
                "available": True,
                "next_part": next_part,
                "start_chapter": start_chapter,
                "end_chapter": end_chapter,
                "title": title,
                "description": description,
                "thumbnail_prompt": thumbnail_prompt,
                "thumbnail_url": thumbnail_url
            })
            
    return jsonify({
        "available": False,
        "next_part": next_part,
        "start_chapter": start_chapter,
        "end_chapter": expected_end,
        "message": "Metadatos no disponibles para este bloque."
    })

@app.route('/images/<path:filename>')
def serve_image(filename):
    """Sirve la imagen para mostrarla en el HTML (incluyendo webp)"""
    return send_from_directory(IMAGE_FOLDER, filename)

@app.route('/api/delete_image', methods=['POST'])
def delete_image():
    """Borra una imagen específica"""
    data = request.json
    rel_path = data.get('path')
    
    if not rel_path:
        return jsonify({"status": "error", "message": "Ruta no proporcionada"}), 400
        
    full_path = os.path.join(IMAGE_FOLDER, rel_path)
    if not os.path.abspath(full_path).startswith(os.path.abspath(IMAGE_FOLDER)):
        return jsonify({"status": "error", "message": "Ruta inválida"}), 403

    try:
        if os.path.exists(full_path):
            os.makedirs(TRASH_FOLDER, exist_ok=True)
            trash_filename = f"{int(time.time() * 1000)}_{os.path.basename(full_path)}"
            trash_path = os.path.join(TRASH_FOLDER, trash_filename)
            shutil.move(full_path, trash_path)
            
            deleted_history.append({"original": full_path, "trashed": trash_path})
            
            return jsonify({"status": "success", "message": "Imagen enviada a papelera"})
        else:
            return jsonify({"status": "error", "message": "La imagen no existe"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/undo_delete', methods=['POST'])
def undo_delete():
    """Restaura la última imagen borrada"""
    if not deleted_history:
        return jsonify({"status": "error", "message": "No hay nada que deshacer"}), 400
        
    last = deleted_history.pop()
    original_path = last["original"]
    trash_path = last["trashed"]
    
    try:
        if os.path.exists(trash_path):
            os.makedirs(os.path.dirname(original_path), exist_ok=True)
            shutil.move(trash_path, original_path)
            return jsonify({"status": "success", "message": "Imagen restaurada con éxito"})
        else:
            return jsonify({"status": "error", "message": "El archivo ya no está en la papelera"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    database.inicializar_db()
    db_manager.init_db()
    print("Iniciando servidor web en http://127.0.0.1:5000")
    # Usa debug=True pero desactiva el reloader si corre en background para evitar crashes de puertos
    app.run(debug=True, use_reloader=False, host='127.0.0.1', port=5000)
