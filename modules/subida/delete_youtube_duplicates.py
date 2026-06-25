import os
import sys
import datetime
import re
import json
import sqlite3
from collections import defaultdict

# Asegurar que el directorio de este script y la raíz del proyecto estén en sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
if script_dir not in sys.path:
    sys.path.append(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    
import youtube_uploader
from modules import db_manager

def extract_manga_hashtag(description):
    # Encontrar hashtags que identifiquen al manga, excluyendo genéricos
    generics = {'shorts', 'manga', 'recap', 'anime', 'isekai', 'manhwa'}
    hashtags = re.findall(r'#(\w+)', description.lower())
    for h in hashtags:
        if h not in generics:
            return h
    return "unknown"

def select_best_video(video_list):
    if not video_list:
        return None
    public_videos = [v for v in video_list if v["privacyStatus"] == "public"]
    if public_videos:
        def sort_public(v):
            try:
                dt = datetime.datetime.fromisoformat(v["publishedAt"].replace('Z', '+00:00'))
                ts = dt.timestamp()
            except Exception:
                ts = 0
            return (-v["views"], ts)
        return sorted(public_videos, key=sort_public)[0]
    else:
        def sort_scheduled(v):
            date_str = v["publishAt"] or v["publishedAt"]
            try:
                dt = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                ts = dt.timestamp()
            except Exception:
                ts = float('inf')
            return ts
        return sorted(video_list, key=sort_scheduled)[0]

def detect_ai_provider(video):
    video_id = video["id"]
    description = video.get("description", "").lower()
    title = video.get("title", "").lower()
    
    # Valores por defecto
    ai = 'gemini'
    manga = 'unknown'
    chapter_or_part = '1'
    type_val = 'short'
    
    # 1. Buscar en la base de datos de shorts (manga_recap.db)
    try:
        db_path = db_manager.DB_PATH
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Buscar en la tabla shorts
            cursor.execute("SELECT manga, youtube_id, is_uploaded FROM shorts")
            for manga_key, yt_id, is_up in cursor.fetchall():
                if yt_id:
                    parts = [p.strip() for p in yt_id.split(",") if p.strip()]
                    if video_id in parts:
                        manga = manga_key
                        type_val = 'short'
                        chapter_or_part = '1'
                        if len(parts) == 2:
                            ai = 'gemini' if parts[0] == video_id else 'ollama'
                        else:
                            ai = 'gemini' if is_up == 1 else 'ollama'
                        conn.close()
                        return ai, manga, chapter_or_part, type_val
                        
            # Buscar en la tabla pipeline_parts
            cursor.execute("SELECT manga, part_number, youtube_id FROM pipeline_parts")
            for manga_key, part_num, yt_id in cursor.fetchall():
                if yt_id:
                    parts = [p.strip() for p in yt_id.split(",") if p.strip()]
                    if video_id in parts:
                        manga = manga_key
                        type_val = 'recap'
                        chapter_or_part = str(part_num)
                        ai = 'gemini'
                        conn.close()
                        return ai, manga, chapter_or_part, type_val
            conn.close()
    except Exception as e:
        print(f"  [WARNING] Error buscando video {video_id} en base de datos: {e}")
        
    # 2. Fallback de texto si no está en la base de datos o falló
    manga_tag = extract_manga_hashtag(video.get("description", ""))
    manga = manga_tag if manga_tag != "unknown" else "unknown"
    
    if "ollama" in description or "ollama" in title:
        ai = 'ollama'
    else:
        ai = 'gemini'
        
    if "#shorts" in description or "#short" in description or "short" in title.lower():
        type_val = 'short'
        chapter_or_part = '1'
    else:
        type_val = 'recap'
        match_part = re.search(r'(?:parte|part|capitulo|cap)\s*(\d+)', title, re.IGNORECASE)
        if match_part:
            chapter_or_part = match_part.group(1)
        else:
            chapter_or_part = '1'
            
    return ai, manga, chapter_or_part, type_val

def log_deleted_video(video, ai_provider, manga, chapter_or_part, type_val):
    try:
        db_path = db_manager.DB_PATH
        
        # 1. Registrar en la base de datos
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            manga_key = manga.replace(' ', '_')
            
            # Insertar en deleted_videos
            cursor.execute('''
                INSERT INTO deleted_videos (manga, type, chapter_or_part, ai_provider, youtube_id, title, description, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending_repair')
            ''', (manga_key, type_val, chapter_or_part, ai_provider, video["id"], video["title"], video["description"]))
            conn.commit()
            conn.close()
            print(f"  [DB] Grabado en deleted_videos: {manga_key} | {type_val} | Parte {chapter_or_part} | IA: {ai_provider}")
            
        # 2. Registrar/actualizar en el JSON logs (resultados tests/videos_eliminados.json)
        os.makedirs("resultados tests", exist_ok=True)
        json_path = "resultados tests/videos_eliminados.json"
        
        log_entry = {
            "id_video_youtube": video["id"],
            "manga": manga,
            "tipo": type_val,
            "capitulo_o_parte": chapter_or_part,
            "ia_proveedor": ai_provider,
            "titulo": video["title"],
            "descripcion": video["description"],
            "motivo_eliminacion": "Duplicado en YouTube (Priorizando Gemini como principal, Ollama secundario)",
            "estado": "pending_repair",
            "eliminado_en": datetime.datetime.now().isoformat()
        }
        
        logs = []
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except Exception:
                logs = []
                
        logs.append(log_entry)
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=4, ensure_ascii=False)
        print(f"  [JSON] Audit log actualizado en {json_path}")
        
    except Exception as e:
        print(f"  [WARNING] Error escribiendo log de eliminación: {e}")

def handle_deleted_video_database_update(video_id, ai_provider, manga, type_val, chapter_or_part):
    try:
        db_path = db_manager.DB_PATH
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            manga_key = manga.replace(' ', '_')
            
            if type_val == 'short':
                cursor.execute("SELECT youtube_id, is_uploaded FROM shorts WHERE manga = ?", (manga_key,))
                row = cursor.fetchone()
                if row:
                    yt_id, is_up = row
                    if yt_id:
                        parts = [p.strip() for p in yt_id.split(",") if p.strip()]
                        if video_id in parts:
                            new_parts = [p for p in parts if p != video_id]
                            if new_parts:
                                new_yt_id = ",".join(new_parts)
                                new_is_up = 1 if ai_provider == 'ollama' else 2
                                cursor.execute("UPDATE shorts SET youtube_id = ?, is_uploaded = ? WHERE manga = ?", (new_yt_id, new_is_up, manga_key))
                                print(f"  [DB] Short '{manga_key}' actualizado: queda ID {new_yt_id} (is_uploaded={new_is_up})")
                            else:
                                cursor.execute("UPDATE shorts SET youtube_id = NULL, is_uploaded = 0, video_created = 0 WHERE manga = ?", (manga_key,))
                                print(f"  [DB] Short '{manga_key}' reseteado: sin videos subidos (is_uploaded=0)")
            else:
                part_num = int(chapter_or_part)
                cursor.execute("UPDATE pipeline_parts SET youtube_id = NULL, is_uploaded = 0 WHERE manga = ? AND part_number = ?", (manga_key, part_num))
                print(f"  [DB] Recap '{manga_key}' Parte {part_num} reseteado: sin video subido (is_uploaded=0)")
                
            conn.commit()
            conn.close()
    except Exception as e:
        print(f"  [WARNING] Error actualizando BD tras eliminación: {e}")

def main():
    print("\n" + "="*60)
    print("   --- DETECTOR Y ELIMINADOR DE VIDEOS DUPLICADOS ---")
    print("="*60)
    
    mock_youtube = os.getenv("MOCK_YOUTUBE", "false").lower() == "true"
    
    try:
        youtube = youtube_uploader.get_authenticated_service()
        if youtube is None:
            raise ValueError("No se pudo obtener el servicio de YouTube autenticado.")
    except Exception as e:
        print(f"  [ERROR] Falló la autenticación con YouTube: {e}")
        return

    if youtube == "MOCK_SERVICE":
        print("\n[MOCK] Ejecutando en modo MOCK. Se simulará la búsqueda y eliminación.")
        mock_run()
        return

    # 1. Obtener la playlist de uploads del canal
    print("Obteniendo canal e identificando lista de subidas...")
    try:
        channels_response = youtube.channels().list(mine=True, part="contentDetails").execute()
        if not channels_response.get("items"):
            print("  [ERROR] No se encontró la información del canal.")
            return
        uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        print(f"  [OK] ID de la lista de subidas: {uploads_playlist_id}")
    except Exception as e:
        print(f"  [ERROR] Error al obtener la lista de subidas: {e}")
        return

    # 2. Paginación de todos los items de la playlist de subidas
    print("\nObteniendo todos los videos del canal...")
    playlist_items = []
    next_page_token = None
    page_count = 1
    
    while True:
        try:
            print(f"  Leyendo página {page_count}...")
            response = youtube.playlistItems().list(
                playlistId=uploads_playlist_id,
                part="snippet,contentDetails,status",
                maxResults=50,
                pageToken=next_page_token
            ).execute()
            
            items = response.get("items", [])
            playlist_items.extend(items)
            print(f"    Encontrados {len(items)} videos en esta página (Total acumulado: {len(playlist_items)})")
            
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
            page_count += 1
        except Exception as e:
            print(f"  [ERROR] Error paginando videos: {e}")
            return

    if not playlist_items:
        print("\nNo se encontraron videos en el canal.")
        return

    # Evitar duplicados de IDs de video obtenidos durante la paginación o en la lista
    seen_ids = set()
    unique_playlist_items = []
    for item in playlist_items:
        vid = item.get("contentDetails", {}).get("videoId")
        if vid and vid not in seen_ids:
            seen_ids.add(vid)
            unique_playlist_items.append(item)
    playlist_items = unique_playlist_items


    # 3. Obtener detalles de cada video en lotes de 50
    print(f"\nConsultando detalles de {len(playlist_items)} videos en lotes de 50...")
    video_details = []
    
    for i in range(0, len(playlist_items), 50):
        batch = playlist_items[i:i+50]
        video_ids = [item["contentDetails"]["videoId"] for item in batch]
        
        try:
            response = youtube.videos().list(
                id=",".join(video_ids),
                part="snippet,status,statistics"
            ).execute()
            
            for item in response.get("items", []):
                video_id = item["id"]
                snippet = item.get("snippet", {})
                status = item.get("status", {})
                statistics = item.get("statistics", {})
                
                title = snippet.get("title", "")
                description = snippet.get("description", "")
                published_at = snippet.get("publishedAt", "")
                privacy_status = status.get("privacyStatus", "private")
                publish_at = status.get("publishAt", None)
                views = int(statistics.get("viewCount", 0))
                
                video_details.append({
                    "id": video_id,
                    "title": title.strip(),
                    "description": description.strip(),
                    "privacyStatus": privacy_status,
                    "publishAt": publish_at,
                    "publishedAt": published_at,
                    "views": views
                })
        except Exception as e:
            print(f"  [WARNING] Error al obtener detalles del lote {i // 50 + 1}: {e}")

    # 4. Agrupar videos por título y manga (usando el primer hashtag no genérico de la descripción)
    videos_by_title = defaultdict(list)
    for video in video_details:
        manga_id = extract_manga_hashtag(video.get("description", ""))
        key = (manga_id, video["title"])
        videos_by_title[key].append(video)

    # 5. Detectar duplicados y decidir cuáles eliminar
    to_delete = []
    to_keep = []
    
    print("\nAnalizando duplicados...")
    for (manga_id, title), group in videos_by_title.items():
        if len(group) == 1:
            v = group[0]
            ai_prov, manga, cap_part, t_val = detect_ai_provider(v)
            v["_ai_provider"] = ai_prov
            v["_manga"] = manga
            v["_chapter_or_part"] = cap_part
            v["_type"] = t_val
            to_keep.append(v)
            continue
            
        manga_str = f" [Manga: #{manga_id}]" if manga_id != "unknown" else ""
        print(f"\nDuplicados detectados para el título: '{title}'{manga_str} ({len(group)} copias)")
        
        gemini_vids = []
        ollama_vids = []
        for v in group:
            ai_prov, manga, cap_part, t_val = detect_ai_provider(v)
            v["_ai_provider"] = ai_prov
            v["_manga"] = manga
            v["_chapter_or_part"] = cap_part
            v["_type"] = t_val
            if ai_prov == 'gemini':
                gemini_vids.append(v)
            else:
                ollama_vids.append(v)
                
        if gemini_vids:
            chosen = select_best_video(gemini_vids)
        else:
            chosen = select_best_video(ollama_vids)
            
        to_keep.append(chosen)
        
        for v in group:
            if v["id"] != chosen["id"]:
                to_delete.append(v)
                sched_info = f"Programado: {v['publishAt']}" if v['publishAt'] else f"Subido: {v['publishedAt']}"
                print(f"  [ELIMINAR] ID: {v['id']} | IA: {v['_ai_provider']} | Estado: {v['privacyStatus']} | Vistas: {v['views']} | {sched_info}")
                
        chosen_sched = f"Programado: {chosen['publishAt']}" if chosen['publishAt'] else f"Subido: {chosen['publishedAt']}"
        print(f"  [CONSERVAR] ID: {chosen['id']} | IA: {chosen['_ai_provider']} | Estado: {chosen['privacyStatus']} | Vistas: {chosen['views']} | {chosen_sched}")

    print("\n" + "="*50)
    print("                 RESUMEN DE OPERACIÓN")
    print("="*50)
    print(f"Total videos analizados: {len(video_details)}")
    print(f"Total grupos (manga/título): {len(videos_by_title)}")
    print(f"Total videos a conservar: {len(to_keep)}")
    print(f"Total videos a eliminar:  {len(to_delete)}")
    print("="*50)

    if not to_delete:
        print("\n¡Excelente! No se encontraron videos duplicados en tu canal.")
        return

    # 6. Eliminar automáticamente
    print("\nIniciando eliminación automática de duplicados...")
    deleted_count = 0
    failed_count = 0
    
    for idx, video in enumerate(to_delete, 1):
        video_id = video["id"]
        title = video["title"]
        print(f"[{idx}/{len(to_delete)}] Eliminando video '{title}' (ID: {video_id})...")
        
        try:
            youtube.videos().delete(id=video_id).execute()
            print("  [OK] Video eliminado con éxito.")
            deleted_count += 1
            ai_provider = video.get("_ai_provider", "unknown")
            manga = video.get("_manga", "unknown")
            chapter_or_part = video.get("_chapter_or_part", "1")
            type_val = video.get("_type", "short")
            log_deleted_video(video, ai_provider, manga, chapter_or_part, type_val)
            handle_deleted_video_database_update(video_id, ai_provider, manga, type_val, chapter_or_part)
        except Exception as e:
            err_msg = str(e).lower()
            if "quota" in err_msg or "limit" in err_msg or "429" in err_msg:
                print(f"\n❌ [CUOTA EXCEDIDA] Se detiene el proceso. Límite de API de YouTube alcanzado.")
                break
            elif "videonotfound" in err_msg or "cannot be found" in err_msg or "404" in err_msg:
                print("  [OK] El video ya no existe o fue eliminado previamente.")
                deleted_count += 1
                ai_provider = video.get("_ai_provider", "unknown")
                manga = video.get("_manga", "unknown")
                chapter_or_part = video.get("_chapter_or_part", "1")
                type_val = video.get("_type", "short")
                log_deleted_video(video, ai_provider, manga, chapter_or_part, type_val)
                handle_deleted_video_database_update(video_id, ai_provider, manga, type_val, chapter_or_part)
            else:
                print(f"  [ERROR] No se pudo eliminar el video: {e}")
                failed_count += 1


    print("\n" + "="*50)
    print("              RESULTADOS DE LA ELIMINACIÓN")
    print("="*50)
    print(f"Videos eliminados con éxito: {deleted_count}")
    print(f"Videos fallidos:             {failed_count}")
    print(f"Videos restantes a eliminar: {len(to_delete) - deleted_count - failed_count}")
    print("="*50)

def mock_run():
    print("\n--- SIMULACIÓN DE DETECCIÓN Y ELIMINACIÓN (MOCK) ---")
    mock_data = [
        {"id": "v1", "title": "Manga Recap 1", "description": "Un gran recap #manga1 #shorts", "privacyStatus": "public", "publishAt": None, "publishedAt": "2026-06-01T10:00:00Z", "views": 150},
        {"id": "v2", "title": "Manga Recap 1", "description": "Un gran recap #manga1 #shorts #ollama", "privacyStatus": "private", "publishAt": "2026-06-01T15:00:00Z", "publishedAt": "2026-06-01T10:05:00Z", "views": 0},
        {"id": "v3", "title": "Manga Recap 2", "description": "Otro recap #manga2 #shorts", "privacyStatus": "private", "publishAt": "2026-06-02T10:00:00Z", "publishedAt": "2026-06-01T11:00:00Z", "views": 0},
        {"id": "v4", "title": "Manga Recap 2", "description": "Otro recap #manga2 #shorts #ollama", "privacyStatus": "private", "publishAt": "2026-06-02T15:00:00Z", "publishedAt": "2026-06-01T11:05:00Z", "views": 0},
        {"id": "v5", "title": "Manga Recap 3", "description": "Recap final #manga3 #shorts", "privacyStatus": "public", "publishAt": None, "publishedAt": "2026-06-03T10:00:00Z", "views": 50},
    ]
    
    videos_by_title = defaultdict(list)
    for video in mock_data:
        manga_id = extract_manga_hashtag(video.get("description", ""))
        key = (manga_id, video["title"])
        videos_by_title[key].append(video)

    to_delete = []
    to_keep = []
    
    for (manga_id, title), group in videos_by_title.items():
        if len(group) == 1:
            v = group[0]
            ai_prov, manga, cap_part, t_val = detect_ai_provider(v)
            v["_ai_provider"] = ai_prov
            v["_manga"] = manga
            v["_chapter_or_part"] = cap_part
            v["_type"] = t_val
            to_keep.append(v)
            continue
            
        manga_str = f" [Manga: #{manga_id}]" if manga_id != "unknown" else ""
        print(f"\nDuplicados detectados (Mock) para: '{title}'{manga_str} ({len(group)} copias)")
        
        gemini_vids = []
        ollama_vids = []
        for v in group:
            ai_prov, manga, cap_part, t_val = detect_ai_provider(v)
            v["_ai_provider"] = ai_prov
            v["_manga"] = manga
            v["_chapter_or_part"] = cap_part
            v["_type"] = t_val
            if ai_prov == 'gemini':
                gemini_vids.append(v)
            else:
                ollama_vids.append(v)
                
        if gemini_vids:
            chosen = select_best_video(gemini_vids)
        else:
            chosen = select_best_video(ollama_vids)
            
        to_keep.append(chosen)
        for v in group:
            if v["id"] != chosen["id"]:
                to_delete.append(v)
                sched_info = f"Programado: {v['publishAt']}" if v['publishAt'] else f"Subido: {v['publishedAt']}"
                print(f"  [ELIMINAR] ID: {v['id']} | IA: {v['_ai_provider']} | Estado: {v['privacyStatus']} | Vistas: {v['views']} | {sched_info}")
                
        chosen_sched = f"Programado: {chosen['publishAt']}" if chosen['publishAt'] else f"Subido: {chosen['publishedAt']}"
        print(f"  [CONSERVAR] ID: {chosen['id']} | IA: {chosen['_ai_provider']} | Estado: {chosen['privacyStatus']} | Vistas: {chosen['views']} | {chosen_sched}")

    print("\n" + "="*50)
    print("                 RESUMEN DE OPERACIÓN (MOCK)")
    print("="*50)
    print(f"Total videos analizados: {len(mock_data)}")
    print(f"Total videos a conservar: {len(to_keep)}")
    print(f"Total videos a eliminar:  {len(to_delete)}")
    print("="*50)
    
    print("\nSimulando eliminación automática de duplicados...")
    for idx, video in enumerate(to_delete, 1):
        print(f"[{idx}/{len(to_delete)}] [MOCK] Eliminando video '{video['title']}' (ID: {video['id']})...")
        print("  [OK] [MOCK] Video eliminado con éxito.")
        
        # Log de auditoría y base de datos en modo mock
        ai_provider = video.get("_ai_provider", "unknown")
        manga = video.get("_manga", "unknown")
        chapter_or_part = video.get("_chapter_or_part", "1")
        type_val = video.get("_type", "short")
        log_deleted_video(video, ai_provider, manga, chapter_or_part, type_val)
        handle_deleted_video_database_update(video["id"], ai_provider, manga, type_val, chapter_or_part)
        
    print("\n  [OK] Simulación completada correctamente.")

if __name__ == "__main__":
    main()
