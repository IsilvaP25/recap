import os
import json
import pickle
import sys
import google.auth.transport.requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError, ResumableUploadError
from dotenv import load_dotenv

# Load env variables from the main project directory
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, 'Proyecto manga recap', '.env'))

# Scopes should match what was used in auth_test.py
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

def get_authenticated_service():
    if os.getenv("MOCK_YOUTUBE", "true").lower() == "true":
        print("[INFO] Modo Mock YouTube activo (MOCK_YOUTUBE=true). Evitando verificación.")
        return "MOCK_SERVICE"

    token_path = os.path.join(os.path.dirname(__file__), 'token.json')
    client_secrets = os.path.join(os.path.dirname(__file__), 'client_secrets.json')
    creds = None
    
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    def authenticate_new():
        if not os.path.exists(client_secrets):
            raise FileNotFoundError(f"No se encontró {client_secrets}. Descárgalo de Google Cloud Console.")
        flow = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES)
        new_creds = flow.run_local_server(port=0)
        with open(token_path, 'wb') as token_file:
            pickle.dump(new_creds, token_file)
        return new_creds

    # Intentar cargar / renovar credenciales existentes
    if creds:
        try:
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    creds.refresh(google.auth.transport.requests.Request())
                    with open(token_path, 'wb') as token:
                        pickle.dump(creds, token)
                else:
                    creds = authenticate_new()
        except Exception as e:
            print(f"  [YouTube] [WARNING] Falló la renovación automática de credenciales: {e}")
            if os.path.exists(token_path):
                try:
                    os.remove(token_path)
                    print("  [YouTube] [INFO] Se eliminó el archivo token.json corrupto o expirado.")
                except Exception as del_err:
                    print(f"  [YouTube] [WARNING] No se pudo eliminar token.json: {del_err}")
            creds = authenticate_new()
    else:
        creds = authenticate_new()
            
    youtube_service = build('youtube', 'v3', credentials=creds)

    # Validar activamente las credenciales contra la API de YouTube
    try:
        # Hacemos una consulta muy ligera para verificar la validez real del token en el servidor
        youtube_service.channels().list(part="id", mine=True).execute()
    except Exception as e:
        err_str = str(e).lower()
        if "quota" in err_str or "limit" in err_str or "429" in err_str:
            print(f"\n[QUOTA_EXCEEDED] Límite de cuota de YouTube alcanzado al validar credenciales: {e}")
            import sys
            sys.exit(42)
        elif "invalid_grant" in err_str or "expired" in err_str or "revoked" in err_str or "credentials" in err_str:
            print(f"  [YouTube] [WARNING] Error de validación con token existente: {e}")
            if os.path.exists(token_path):
                try:
                    os.remove(token_path)
                    print("  [YouTube] [INFO] Token inválido en el servidor. Se eliminó token.json y se abrirá el navegador para re-autenticar...")
                except Exception as del_err:
                    print(f"  [YouTube] [WARNING] No se pudo eliminar token.json: {del_err}")
            creds = authenticate_new()
            youtube_service = build('youtube', 'v3', credentials=creds)
        else:
            raise

    return youtube_service

def get_channel_info(youtube):
    if youtube == "MOCK_SERVICE":
        return "Canal Mock (YouTube Desactivado)"
    try:
        request = youtube.channels().list(part="snippet", mine=True)
        response = request.execute()
        if 'items' in response and len(response['items']) > 0:
            return response['items'][0]['snippet']['title']
        raise ValueError("Canal no encontrado o sin información.")
    except Exception as e:
        # En caso de cualquier error residual no detectado antes, intentamos limpiar el token
        err_str = str(e).lower()
        if "invalid_grant" in err_str or "expired" in err_str or "revoked" in err_str or "credentials" in err_str:
            token_path = os.path.join(os.path.dirname(__file__), 'token.json')
            if os.path.exists(token_path):
                try:
                    os.remove(token_path)
                except Exception:
                    pass
        raise

def upload_video(youtube, file_path, title, description, category="22", tags=None, privacy="public"):
    print(f"--- Subiendo Video: {title} ---")
    if youtube == "MOCK_SERVICE":
        print(f"[MOCK] Video subido con éxito (Mock ID). Archivo: {file_path}")
        return "mock_video_id_12345"
        
    body = {
        'snippet': {
            'title': title[:100],
            'description': description,
            'tags': tags or [],
            'categoryId': category
        },
        'status': {
            'privacyStatus': privacy,
            'selfDeclaredMadeForKids': False
        }
    }
    
    try:
        media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"  Progreso: {int(status.progress() * 100)}%")
                
        print(f"[OK] Video subido con ID: {response['id']}")
        return response['id']
    except (HttpError, ResumableUploadError) as e:
        err_msg = str(e)
        if "quota" in err_msg.lower() or "limit" in err_msg.lower() or "429" in err_msg:
            print(f"\n[QUOTA_EXCEEDED] Límite de subidas de YouTube alcanzado en upload_video: {e}")
            sys.exit(42)
        else:
            print(f"\n[ERROR] Error en la subida en upload_video: {e}")
            sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Error inesperado en upload_video: {e}")
        sys.exit(1)

def upload_thumbnail(youtube, video_id, thumb_path):
    print(f"--- Subiendo Miniatura para {video_id} ---")
    if youtube == "MOCK_SERVICE":
        print(f"[MOCK] Miniatura subida con éxito para {video_id}. Archivo: {thumb_path}")
        return True
        
    if not os.path.exists(thumb_path):
        print(f"  [ERROR] Miniatura no encontrada: {thumb_path}")
        return False
        
    youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumb_path)).execute()
    print("[OK] Miniatura establecida.")
    return True

def get_or_create_playlist(youtube, manga_title):
    # Truncar a un máximo de 100 caracteres por seguridad de límites de la API de YouTube
    if len(manga_title) > 100:
        manga_title = manga_title[:97] + "..."
        
    if youtube == "MOCK_SERVICE":
        return "mock_playlist_id_12345"
        
    # Find existing playlist
    request = youtube.playlists().list(part="snippet", mine=True, maxResults=50)
    response = request.execute()
    
    for item in response.get('items', []):
        if item['snippet']['title'] == manga_title:
            return item['id']
            
    # Create new if not found
    print(f"  [PLAYLIST] Creando nueva lista: {manga_title}")
    body = {
        'snippet': {
            'title': manga_title,
            'description': f"Recaps automáticos de {manga_title}"
        }
    }
    response = youtube.playlists().insert(part="snippet", body=body).execute()
    return response['id']

def add_to_playlist(youtube, playlist_id, video_id):
    if youtube == "MOCK_SERVICE":
        print(f"[MOCK] Video {video_id} añadido a la lista {playlist_id} con éxito.")
        return
        
    body = {
        'snippet': {
            'playlistId': playlist_id,
            'resourceId': {
                'kind': 'youtube#video',
                'videoId': video_id
            }
        }
    }
    youtube.playlistItems().insert(part="snippet", body=body).execute()
def wait_for_processing(youtube, video_id, check_interval=30):
    if youtube == "MOCK_SERVICE":
        print(f"  [MOCK YouTube] Esperando procesamiento del video (ID: {video_id})...")
        import time
        time.sleep(2)
        print("  [MOCK YouTube] El video ha sido procesado por completo!")
        return True
        
    print(f"  [YouTube] Esperando procesamiento del video (ID: {video_id})...")
    import time
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
                print(f"  [YouTube] No se encontró el video con ID {video_id}.")
                return False
                
            status = response["items"][0]["status"]
            upload_status = status.get("uploadStatus")
            
            print(f"  [YouTube] [Consulta {attempts+1}] Estado actual de YouTube: {upload_status}")
            
            if upload_status == "processed":
                print("  [YouTube] El video ha sido procesado por completo!")
                return True
            elif upload_status in ["failed", "rejected"]:
                print(f"  [YouTube] El procesamiento falló en YouTube. Estado: {upload_status}")
                return False
        except Exception as e:
            print(f"  [YouTube] Error consultando estado: {e}")
            
        attempts += 1
        time.sleep(check_interval)
        
    print("  [YouTube] Se alcanzó el tiempo de espera límite sin completarse el procesamiento.")
    return False
def clean_title(title, manga_name):
    import re
    # Normalize and build variants
    variants = [
        manga_name,
        manga_name.replace('_', ' '),
        manga_name.replace(' ', '_'),
    ]
    # Remove duplicates and empty strings, sort by length descending
    variants = sorted(list(set(v.strip() for v in variants if v.strip())), key=len, reverse=True)
    
    cleaned = title
    for var in variants:
        pattern = re.compile(re.escape(var), re.IGNORECASE)
        cleaned = pattern.sub("", cleaned)
        
    # Clean up double spaces or spaces around remaining text
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # Remove leftover separators at boundaries (beginning, end, or before hashtags)
    # Separators: - – — : |
    cleaned = re.sub(r'^\s*[-–—:|]\s*', '', cleaned)
    # Matches separator before hashtags or at the end
    cleaned = re.sub(r'\s*[-–—:|]\s*(?=#|$)', '', cleaned)
    
    # Clean up sequenced connectors/prepositions like "de de", "de a", "de en", "de para", "del al", "de del"
    # When replacing, we keep the second preposition (e.g. "de a" -> "a", "de en" -> "en")
    cleaned = re.sub(r'\b(de|del|of|con|en)\s+(a|en|para|por|de|del|of|con|al)\b', r'\2', cleaned, flags=re.IGNORECASE)
    
    # Remove leftover connectors followed by punctuation, space-question mark, emoji, hashtag or end of string
    connector_pat = re.compile(r'\b(de|del|of|con|with|vs|contra|en|sobre)\b\s*(?=[?!\.#\-\–\—\|]|$)', re.IGNORECASE)
    cleaned = connector_pat.sub("", cleaned)
    
    # Let's clean up space before question marks or punctuation
    cleaned = re.sub(r'\s+([?!\.,])', r'\1', cleaned)
    
    # Clean up double spaces again
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # Let's run a secondary pass to remove separators that might have been exposed
    cleaned = re.sub(r'^\s*[-–—:|]\s*', '', cleaned)
    cleaned = re.sub(r'\s*[-–—:|]\s*(?=#|$)', '', cleaned)
    
    # If the title ends up empty or only punctuation/emojis, return a fallback
    if not re.search(r'[a-zA-Z0-9]', cleaned):
        emojis = "".join(c for c in cleaned if ord(c) > 0x1000 or c in "😱🤯💔😈😭")
        cleaned = f"¿EL FINAL QUE NO ESPERABAS? {emojis}".strip()
        
    return cleaned

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--thumb", required=False)
    parser.add_argument("--json", required=True, help="Archivo JSON con los metadatos de YouTube")
    parser.add_argument("--manga", required=True)
    parser.add_argument("--schedule", required=False) # Nueva opción: ISO date string
    args = parser.parse_args()
    
    youtube = get_authenticated_service()
    if youtube:
        if not os.path.exists(args.json):
            print(f"  [ERROR] El archivo de metadatos JSON no existe: {args.json}")
            import sys
            sys.exit(1)
            
        try:
            with open(args.json, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as e:
            print(f"  [ERROR] Error leyendo el archivo JSON de metadatos: {e}")
            import sys
            sys.exit(1)
            
        # Lógica de Privacidad y Programación
        privacy_status = 'public'
        publish_at = None
        
        if args.schedule:
            privacy_status = 'private' # Obligatorio para programar
            publish_at = args.schedule
            print(f"  [PROGRAMACIÓN] Estreno fijado para: {publish_at}")

        # Insertar body con publishAt si existe
        raw_title = meta.get('clickbait_title', f"{args.manga} Recap")
        cleaned_title = clean_title(raw_title, args.manga)[:100]
        body = {
            'snippet': {
                'title': cleaned_title,
                'description': meta.get('description', f"Recap of {args.manga}"),
                'tags': meta.get('tags', []),
                'categoryId': "22"
            },
            'status': {
                'privacyStatus': privacy_status,
                'selfDeclaredMadeForKids': False
            }
        }
        if publish_at:
            body['status']['publishAt'] = publish_at

        if youtube == "MOCK_SERVICE":
            import time
            video_id = f"mock_yt_{int(time.time())}"
            print(f"[MOCK] Datos del snippet de subida:")
            print(f"  - Título: {body['snippet']['title']}")
            print(f"  - Descripción: {body['snippet']['description']}")
            print(f"  - Tags: {body['snippet']['tags']}")
            print(f"Video subido con ID: {video_id}")
            print(f"\n[DONE] PROCESO COMPLETADO: https://youtu.be/{video_id}")
            import sys
            sys.exit(0)

        try:
            media = MediaFileUpload(args.video, chunksize=-1, resumable=True)
            request = youtube.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status: print(f"  Progreso: {int(status.progress() * 100)}%")
                
            video_id = response['id']
            print(f"[OK] Video subido con ID: {video_id}")
        except (HttpError, ResumableUploadError) as e:
            err_msg = str(e)
            if "quota" in err_msg.lower() or "limit" in err_msg.lower() or "429" in err_msg:
                print(f"\n[QUOTA_EXCEEDED] Límite de subidas de YouTube alcanzado: {e}")
                sys.exit(42)
            else:
                print(f"\n[ERROR] Error en la subida de YouTube: {e}")
                sys.exit(1)
        except Exception as e:
            print(f"\n[ERROR] Error inesperado en la subida: {e}")
            sys.exit(1)
        
        if video_id:
            if args.thumb:
                try:
                    upload_thumbnail(youtube, video_id, args.thumb)
                except Exception as e:
                    print(f"  [WARNING] No se pudo subir la miniatura: {e}")
            
            try:
                playlist_id = get_or_create_playlist(youtube, args.manga.replace('_', ' '))
                if playlist_id:
                    add_to_playlist(youtube, playlist_id, video_id)
            except Exception as e:
                print(f"  [WARNING] No se pudo agregar a la lista de reproduccion: {e}")
                
            print(f"\n[DONE] PROCESO COMPLETADO: https://youtu.be/{video_id}")

            # Esperar a que el video sea procesado. La eliminación del archivo local se delega al orquestador.
            print(f"\n[YouTube] Esperando procesamiento de YouTube...")
            if wait_for_processing(youtube, video_id, check_interval=30):
                print(f"[INFO] El video se procesó correctamente. La eliminación del archivo local se delega al orquestador: {args.video}")
            else:
                print(f"  [WARNING] El video no se procesó correctamente o se agotó el tiempo de espera: {args.video}")
