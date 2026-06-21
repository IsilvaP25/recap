import os
import requests
import re
from modules import database

def descargar_portada(manga_id, manga_titulo):
    """Descarga la portada oficial del manga y la guarda en la carpeta COVER."""
    from modules import manga_search
    print(f"  [COVER] Descargando portada oficial...")
    details = manga_search.obtener_detalles_completos(manga_id)
    thumb_url = details.get("thumb")
    
    if not thumb_url:
        print("  [AVISO] No se encontró URL de portada.")
        return None
        
    from modules import utils
    m_folder_clean = utils.sanitizar_nombre_carpeta(manga_titulo)
    base_proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cover_dir = os.path.join(base_proj, "outputs", m_folder_clean, "COVER")
    os.makedirs(cover_dir, exist_ok=True)
    
    ext = thumb_url.split('.')[-1].split('?')[0]
    if len(ext) > 4 or not ext:
        ext = 'jpg'
    cover_path = os.path.join(cover_dir, f"official_cover.{ext}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        res = requests.get(thumb_url, headers=headers, stream=True)
        if res.status_code == 200:
            with open(cover_path, "wb") as f:
                for chunk in res.iter_content(1024):
                    f.write(chunk)
            print(f"  [OK] Portada guardada en: {cover_path}")
            return cover_path
    except Exception as e:
        print(f"  [ERROR] Al descargar portada: {e}")
    return None

def obtener_urls_imagenes(chapter_id):
    from bs4 import BeautifulSoup
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(chapter_id, headers=headers)
        if response.status_code != 200:
            return None, []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        scripts = soup.find_all('script')
        
        for script in scripts:
            if script.string and 'var yutas' in script.string:
                match = re.search(r'var\s+yutas\s*=\s*\[(.*?)\];', script.string, re.DOTALL)
                if match:
                    contenido_array = match.group(1)
                    urls = re.findall(r"'(https?://[^']+)'", contenido_array)
                    if urls:
                        return response, urls
                        
            if script.string and 'thzq' in script.string:
                match = re.search(r'var\s+thzq\s*=\s*\[(.*?)\];', script.string, re.DOTALL)
                if match:
                    contenido_array = match.group(1)
                    urls = re.findall(r"'(https?://[^']+)'", contenido_array)
                    if urls:
                        return response, urls
        return response, []
    except Exception as e:
        print(f"Error al obtener páginas del capítulo {chapter_id}: {e}")
        return None, []

def descargar_imagen_individual(session, img_url, ruta_archivo, chapter_id, headers):
    try:
        # Soporte para reanudar descarga (si ya existe, saltamos)
        if os.path.exists(ruta_archivo) and os.path.getsize(ruta_archivo) > 0:
            return True
            
        img_res = session.get(img_url, headers=headers, timeout=20)
        if img_res.status_code == 200:
            with open(ruta_archivo, 'wb') as f:
                f.write(img_res.content)
            database.insertar_imagen(chapter_id, img_url, ruta_archivo)
            return True
        return False
    except Exception:
        return False

def descargar_capitulo(manga_titulo, chapter_id, num_capitulo):
    response, imagenes = obtener_urls_imagenes(chapter_id)
    
    if not imagenes:
        print(f"No se encontraron imagenes para el capitulo {num_capitulo}")
        return response

    from modules import utils
    m_folder_clean = utils.sanitizar_nombre_carpeta(manga_titulo)
    # Ruta absoluta al proyecto
    base_proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ruta_base = os.path.join(base_proj, "raw_downloads", m_folder_clean, f"Capitulo_{num_capitulo}")
    os.makedirs(ruta_base, exist_ok=True)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://mangakatana.com/'
    }

    # 1. Preparar las rutas de destino de las imágenes
    tareas = []
    for i, img_url in enumerate(imagenes):
        ext = img_url.split('.')[-1].split('?')[0]
        if len(ext) > 4 or not ext:
            ext = 'jpg'
        
        nombre_archivo = f"{str(i+1).zfill(3)}.{ext}"
        ruta_archivo = os.path.join(ruta_base, nombre_archivo)
        tareas.append((img_url, ruta_archivo))

    # 2. Descarga concurrente con hilos (ThreadPoolExecutor) y sesión persistente
    from concurrent.futures import ThreadPoolExecutor
    session = requests.Session()

    class ConcurrentProgress:
        def __init__(self, futures_list):
            self.futures = futures_list
        def __len__(self):
            return len(self.futures)
        def __iter__(self):
            from concurrent.futures import as_completed
            for future in as_completed(self.futures):
                yield future.result()

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(descargar_imagen_individual, session, img_url, ruta_archivo, chapter_id, headers)
            for img_url, ruta_archivo in tareas
        ]

        todos_exitosos = True
        for res in utils.barra_progreso(ConcurrentProgress(futures), prefijo=f"Descargando {len(imagenes)} imagenes"):
            if not res:
                todos_exitosos = False

    if todos_exitosos:
        database.marcar_capitulo_descargado(chapter_id)
    else:
        print(f"\n  [WARNING] No se pudieron descargar algunas imágenes del Capítulo {num_capitulo}.")

    return response