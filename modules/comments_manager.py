import os
import sys
import sqlite3
import datetime
import random

# Ensure parent directory is in path for imports
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT_DIR = os.path.dirname(BASE_DIR)
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

from modules import database
from modules.pipeline import db_manager

def get_youtube_video_mapping():
    """Construye un mapa de youtube_id -> manga_key a partir de shorts y pipeline_parts."""
    conn = database.conectar()
    cursor = conn.cursor()
    
    mapping = {}
    
    # 1. Mapear desde shorts (pueden ser múltiples IDs separados por coma)
    cursor.execute("SELECT manga, youtube_id FROM shorts WHERE youtube_id IS NOT NULL")
    for manga, yt_ids in cursor.fetchall():
        if not yt_ids:
            continue
        # Separar por comas por si hay subidas dobles
        ids = [x.strip() for x in yt_ids.split(',') if x.strip()]
        for vid_id in ids:
            mapping[vid_id] = manga
            
    # 2. Mapear desde pipeline_parts
    cursor.execute("SELECT manga, youtube_id FROM pipeline_parts WHERE youtube_id IS NOT NULL")
    for manga, yt_id in cursor.fetchall():
        if yt_id:
            mapping[yt_id] = manga
            
    conn.close()
    return mapping

def generar_comentarios_simulados():
    """Genera comentarios de prueba realistas para los mangas que tienen videos subidos o programados."""
    mapping = get_youtube_video_mapping()
    if not mapping:
        # Si no hay mapeo, buscar mangas en la base de datos para simular
        conn = database.conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM mangas LIMIT 5")
        mangas = [m[0] for m in cursor.fetchall()]
        conn.close()
        # Mapear IDs ficticios
        for i, m_id in enumerate(mangas):
            # Obtener nombre de carpeta sanitizado
            from modules.utils import sanitizar_nombre_carpeta
            cursor = database.conectar().cursor()
            cursor.execute("SELECT titulo FROM mangas WHERE id = ?", (m_id,))
            titulo = cursor.fetchone()[0]
            m_key = sanitizar_nombre_carpeta(titulo)
            mapping[f"mock_vid_{i}"] = m_key

    autores = [
        "MangaFan99", "OtakuGamer", "Pedro_Recaps", "SofiaManga", "GokuSuper", 
        "Alex_Reading", "Luna_Manga", "JuanMendoza", "CrunchyRoller", "SoloLeveler"
    ]
    
    plantillas_comentarios = [
        "¡Excelente recap! ¿Cuándo subes la siguiente parte de este manga?",
        "No conocía esta serie, me llamó mucho la atención la sinopsis. ¡Buen video!",
        "La portada se ve increíble. ¿Cuántos capítulos tiene en total?",
        "¡Me encanta este canal! Sigue trayendo más recaps de este tipo.",
        "Quedé con ganas de ver más capítulos... ¿Se puede descargar el manga completo en algún lado?",
        "Gran edición de video y el guion está muy bien adaptado. Susscrito.",
        "¿Este es el manga que está en emisión? Espero que subas la continuación pronto.",
        "Muy buen resumen, me ahorró leer los primeros capítulos jajaja.",
        "Por favor continúa subiendo esta serie, está buenísima.",
        "¡Me vi el short y vine a ver si había más! Sube la parte 2 porfa."
    ]

    conn = database.conectar()
    cursor = conn.cursor()
    
    comentarios_creados = 0
    ahora = datetime.datetime.now()
    
    for vid_id, manga_key in mapping.items():
        # Generar entre 1 y 2 comentarios por video
        num_comentarios = random.randint(1, 2)
        for c_idx in range(num_comentarios):
            c_id = f"mock_comment_{vid_id}_{c_idx}"
            
            # Verificar si ya existe
            cursor.execute("SELECT COUNT(*) FROM comentarios WHERE id = ?", (c_id,))
            if cursor.fetchone()[0] > 0:
                continue
                
            autor = random.choice(autores)
            texto = random.choice(plantillas_comentarios)
            # Fecha simulada hace unas horas
            d_time = ahora - datetime.timedelta(hours=random.randint(1, 48))
            fecha_pub = d_time.isoformat()
            
            cursor.execute("""
                INSERT OR IGNORE INTO comentarios (id, youtube_video_id, manga_key, autor, texto, fecha_publicacion, leido)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            """, (c_id, vid_id, manga_key, autor, texto, fecha_pub))
            comentarios_creados += 1
            
    conn.commit()
    conn.close()
    print(f"[COMMENTS_MANAGER] Generados {comentarios_creados} comentarios simulados para pruebas.")
    return comentarios_creados

def sincronizar_comentarios_canal():
    """Sincroniza comentarios de YouTube. Usa mock como fallback si MOCK_YOUTUBE=true o falla la autenticación."""
    mock_youtube = os.getenv("MOCK_YOUTUBE", "false").lower() == "true"
    
    if mock_youtube:
        print("[COMMENTS_MANAGER] Modo Mock activo. Iniciando generación de comentarios simulados...")
        generar_comentarios_simulados()
        return {"status": "success", "message": "Sincronización simulada completada con éxito."}

    try:
        from api import youtube_uploader
        youtube = youtube_uploader.get_authenticated_service()
        
        if youtube == "MOCK_SERVICE":
            print("[COMMENTS_MANAGER] Servicio autenticado devolvió MOCK_SERVICE. Usando comentarios simulados...")
            generar_comentarios_simulados()
            return {"status": "success", "message": "Sincronización simulada completada con éxito (Servicio MOCK)."}
            
        # 1. Obtener ID del canal
        channels_response = youtube.channels().list(part="id", mine=True).execute()
        if not channels_response.get("items"):
            raise ValueError("No se encontró información del canal autenticado.")
        channel_id = channels_response["items"][0]["id"]
        
        print(f"[COMMENTS_MANAGER] Consultando comentarios para el canal ID: {channel_id}")
        
        # 2. Descargar últimos 100 hilos de comentarios del canal
        # allThreadsRelatedToChannelId obtiene comentarios del canal entero (incluidos los de sus videos)
        threads_response = youtube.commentThreads().list(
            part="snippet",
            allThreadsRelatedToChannelId=channel_id,
            maxResults=100
        ).execute()
        
        threads = threads_response.get("items", [])
        print(f"[COMMENTS_MANAGER] Se obtuvieron {len(threads)} hilos de comentarios de YouTube.")
        
        # 3. Obtener mapa de videos locales
        video_mapping = get_youtube_video_mapping()
        
        conn = database.conectar()
        cursor = conn.cursor()
        
        sincronizados = 0
        for thread in threads:
            snippet = thread.get("snippet", {})
            videoId = snippet.get("videoId")
            
            # Si el video pertenece a uno de nuestros mangas registrados
            if videoId in video_mapping:
                manga_key = video_mapping[videoId]
                top_comment = snippet.get("topLevelComment", {})
                comment_id = top_comment.get("id")
                
                if not comment_id:
                    continue
                    
                comment_snippet = top_comment.get("snippet", {})
                autor = comment_snippet.get("authorDisplayName", "Usuario Anónimo")
                texto = comment_snippet.get("textDisplay", "")
                fecha_pub = comment_snippet.get("publishedAt", "")
                
                # Insertar en comentarios omitiendo duplicados (INSERT OR IGNORE)
                # Esto asegura que si ya existe, no se altere su estado 'leido'
                cursor.execute("""
                    INSERT OR IGNORE INTO comentarios (id, youtube_video_id, manga_key, autor, texto, fecha_publicacion, leido)
                    VALUES (?, ?, ?, ?, ?, ?, 0)
                """, (comment_id, videoId, manga_key, autor, texto, fecha_pub))
                
                if cursor.rowcount > 0:
                    sincronizados += 1
                    
        conn.commit()
        conn.close()
        
        print(f"[COMMENTS_MANAGER] Sincronización exitosa. Guardados {sincronizados} nuevos comentarios.")
        return {"status": "success", "message": f"Sincronización exitosa. Se importaron {sincronizados} nuevos comentarios."}
        
    except Exception as e:
        print(f"[COMMENTS_MANAGER] [ERROR] Falló la sincronización con YouTube: {e}. Usando fallback de comentarios simulados.")
        # Fallback a mock en caso de error de red o cuota excedida
        generar_comentarios_simulados()
        return {"status": "success", "message": f"Sincronización YouTube fallida ({e}). Se cargaron comentarios de simulación."}
