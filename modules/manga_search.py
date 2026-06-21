import requests
from bs4 import BeautifulSoup
import re
import random
import urllib.parse

def obtener_pool_mangas(pagina=1):
    url_lista = f'https://mangakatana.com/manga/page/{pagina}?filter=1&order=latest'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url_lista, headers=headers)
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        uk_book = soup.find('div', {'id': 'book_list'}) or soup.find('div', {'class': 'uk-grid'})
        if not uk_book:
            return []
            
        titulos = uk_book.find_all('h3', {'class': 'title'})
        pool_mangas = []
        
        for t in titulos:
            enlace = t.find('a')
            if enlace and enlace.get('href') and enlace.text.strip():
                limpio = "".join([c for c in enlace.text.strip() if c.isalnum() or c in (' ', '_', '-')]).rstrip()
                pool_mangas.append({
                    'titulo': limpio,
                    'url': enlace.get('href')
                })
        
        return list({m['url']: m for m in pool_mangas}.values())
    except Exception:
        return []

def buscar_por_titulo(query):
    url = f"https://mangakatana.com/?search={urllib.parse.quote(query)}&search_by=book_name"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check if we were redirected directly to a manga details page
        # Mangakatana redirects to the book page if there is exactly 1 match
        if soup.find('div', {'class': 'cover'}) and soup.find('h1', {'class': 'heading'}):
            title_tag = soup.find('h1', {'class': 'heading'})
            title = title_tag.text.strip() if title_tag else "Manga"
            limpio = "".join([c for c in title if c.isalnum() or c in (' ', '_', '-')]).rstrip()
            
            url_portada = None
            contenedor_img = soup.find('div', {'class': 'cover'}) or soup.find('div', {'class': 'media'})
            if contenedor_img:
                img_tag = contenedor_img.find('img')
                if img_tag:
                    url_portada = img_tag.get('data-src') or img_tag.get('src')
            if not url_portada:
                img_tag = soup.find('img', {'alt': lambda x: x and 'cover' in x.lower()})
                if img_tag:
                    url_portada = img_tag.get('data-src') or img_tag.get('src')
            
            tabla_capitulos = soup.find('div', {'class': 'chapters'})
            num_chapters = len(tabla_capitulos.find_all('a')) if tabla_capitulos else 0
            
            status = "ongoing"
            info_div = soup.find('div', {'class': 'info'})
            if info_div and "completed" in info_div.text.lower():
                status = "completed"
                
            return [{
                "id": response.url,
                "title": limpio,
                "thumb": url_portada,
                "total_chapter": num_chapters,
                "status": status,
                "type": "manga"
            }]
            
        uk_book = soup.find('div', {'id': 'book_list'}) or soup.find('div', {'class': 'uk-grid'})
        if not uk_book:
            return []
            
        items = uk_book.find_all('div', {'class': 'item'})
        resultados = []
        
        for item in items:
            t = item.find('h3', {'class': 'title'})
            if not t:
                continue
            enlace = t.find('a')
            if not (enlace and enlace.get('href') and enlace.text.strip()):
                continue
                
            limpio = "".join([c for c in enlace.text.strip() if c.isalnum() or c in (' ', '_', '-')]).rstrip()
            manga_url = enlace.get('href')
            
            thumb_url = ""
            img_container = item.find('div', {'class': 'image'})
            if img_container:
                img_tag = img_container.find('img')
                if img_tag:
                    thumb_url = img_tag.get('data-src') or img_tag.get('src') or ""
            
            resultados.append({
                "id": manga_url,
                "title": limpio,
                "thumb": thumb_url,
                "total_chapter": "?",
                "status": "ongoing",
                "type": "manga"
            })
            
        return list({m['id']: m for m in resultados}.values())
    except Exception as e:
        print(f"Error en buscar_por_titulo: {e}")
        return []

def obtener_manga_aleatorio(return_list=False):
    page = random.randint(1, 5)
    pool = obtener_pool_mangas(page)
    if not pool:
        return [] if return_list else None
    
    formatted_pool = []
    for item in pool:
        formatted_pool.append({
            "id": item['url'],
            "title": item['titulo'],
            "thumb": "",
            "total_chapter": "?",
            "status": "ongoing",
            "type": "manga"
        })
    
    if return_list:
        return formatted_pool
    return random.choice(formatted_pool)

def obtener_detalles_completos(manga_id):
    url = manga_id if manga_id.startswith('http') else f"https://mangakatana.com/manga/{manga_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return {}
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Title
        title_tag = soup.find('h1', {'class': 'heading'})
        title = title_tag.text.strip() if title_tag else "Manga"
        limpio = "".join([c for c in title if c.isalnum() or c in (' ', '_', '-')]).rstrip()
        
        # Cover
        url_portada = None
        contenedor_img = soup.find('div', {'class': 'cover'}) or soup.find('div', {'class': 'media'})
        if contenedor_img:
            img_tag = contenedor_img.find('img')
            if img_tag:
                url_portada = img_tag.get('data-src') or img_tag.get('src')
        if not url_portada:
            img_tag = soup.find('img', {'alt': lambda x: x and 'cover' in x.lower()})
            if img_tag:
                url_portada = img_tag.get('data-src') or img_tag.get('src')
        
        # Summary
        summary = ""
        summary_tag = soup.find('div', {'class': 'summary'})
        if summary_tag:
            p_tag = summary_tag.find('p')
            summary = p_tag.text.strip() if p_tag else summary_tag.text.strip()
            
        # Chapters list
        tabla_capitulos = soup.find('div', {'class': 'chapters'})
        lista_capitulos = []
        if tabla_capitulos:
            rows = tabla_capitulos.find_all('tr')
            for row in rows:
                ch_div = row.find('div', {'class': 'chapter'})
                if ch_div:
                    enc = ch_div.find('a')
                    if enc and enc.get('href'):
                        date_div = row.find('div', {'class': 'update_time'})
                        date_str = date_div.text.strip() if date_div else ""
                        lista_capitulos.append({
                            'capitulo': enc.text.strip(),
                            'url': enc.get('href'),
                            'date': date_str
                        })
            if not lista_capitulos:
                enlaces = tabla_capitulos.find_all('a')
                for enc in enlaces:
                    if enc.get('href'):
                        lista_capitulos.append({
                            'capitulo': enc.text.strip(),
                            'url': enc.get('href'),
                            'date': ""
                        })
        
        total_chapters = len(lista_capitulos)
        
        # Status / Type
        status = "ongoing"
        manga_type = "manga"
        info_div = soup.find('div', {'class': 'info'})
        if info_div:
            info_text = info_div.text.lower()
            if "completed" in info_text:
                status = "completed"
            if "manhwa" in info_text:
                manga_type = "manhwa"
            elif "manhua" in info_text:
                manga_type = "manhua"
                
        return {
            "id": manga_id,
            "title": limpio,
            "summary": summary,
            "thumb": url_portada,
            "total_chapter": total_chapters,
            "status": status,
            "type": manga_type,
            "chapters": lista_capitulos[::-1] # oldest to newest
        }
    except Exception as e:
        print(f"Error al obtener detalles completos para {manga_id}: {e}")
        return {}

# Lista estática de géneros disponibles en MangaKatana
GENRES = {
    "4-koma": "4-koma",
    "Action": "action",
    "Adult": "adult",
    "Adventure": "adventure",
    "Artbook": "artbook",
    "Award Winning": "award-winning",
    "Comedy": "comedy",
    "Cooking": "cooking",
    "Doujinshi": "doujinshi",
    "Drama": "drama",
    "Ecchi": "ecchi",
    "Erotica": "erotica",
    "Fantasy": "fantasy",
    "Gender Bender": "gender-bender",
    "Gore": "gore",
    "Harem": "harem",
    "Historical": "historical",
    "Horror": "horror",
    "Isekai": "isekai",
    "Josei": "josei",
    "Loli": "loli",
    "Manhua": "manhua",
    "Manhwa": "manhwa",
    "Martial Arts": "martial-arts",
    "Mecha": "mecha",
    "Medical": "medical",
    "Music": "music",
    "Mystery": "mystery",
    "One-shot": "one-shot",
    "Overpowered MC": "overpowered-mc",
    "Psychological": "psychological",
    "Reincarnation": "reincarnation",
    "Romance": "romance",
    "School Life": "school-life",
    "Sci-fi": "sci-fi",
    "Seinen": "seinen",
    "Sexual Violence": "sexual-violence",
    "Shota": "shota",
    "Shoujo": "shoujo",
    "Shoujo Ai": "shoujo-ai",
    "Shounen": "shounen",
    "Shounen Ai": "shounen-ai",
    "Slice of Life": "slice-of-life",
    "Sports": "sports",
    "Super Power": "super-power",
    "Supernatural": "supernatural",
    "Survival": "survival",
    "Time Travel": "time-travel",
    "Tragedy": "tragedy",
    "Webtoon": "webtoon",
    "Yaoi": "yaoi",
    "Yuri": "yuri"
}

def buscar_por_genero_y_ano(genre_value, year_min, limit=15, max_pages=15, skip_urls=None):
    """
    Busca mangas de un género específico en el directorio de MangaKatana
    y los filtra para devolver solo aquellos lanzados desde el año mínimo en adelante.
    """
    if skip_urls is None:
        skip_urls = set()
    print(f"\nBuscando mangas con género '{genre_value}' desde el año {year_min} en adelante...")
    resultados = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # Llevar registro de URLs procesadas para evitar duplicados
    urls_procesadas = set()
    
    for page in range(1, max_pages + 1):
        if len(resultados) >= limit:
            break
            
        url = f"https://mangakatana.com/manga/page/{page}?filter=1&include_genre_chk={genre_value}&include_mode=and&order=latest"
        print(f"Buscando en la página {page} del directorio...")
        try:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            uk_book = soup.find('div', {'id': 'book_list'}) or soup.find('div', {'class': 'uk-grid'})
            if not uk_book:
                break
                
            items = uk_book.find_all('div', {'class': 'item'})
            if not items:
                break
                
            for item in items:
                if len(resultados) >= limit:
                    break
                    
                t = item.find('h3', {'class': 'title'})
                if not t:
                    continue
                enlace = t.find('a')
                if not (enlace and enlace.get('href') and enlace.text.strip()):
                    continue
                    
                manga_url = enlace.get('href')
                if manga_url in urls_procesadas or manga_url in skip_urls:
                    continue
                urls_procesadas.add(manga_url)
                
                titulo = "".join([c for c in enlace.text.strip() if c.isalnum() or c in (' ', '_', '-')]).rstrip()
                
                # Consultar detalles completos para obtener la fecha del primer capítulo
                detalles = obtener_detalles_completos(manga_url)
                if not detalles or not detalles.get("chapters"):
                    continue
                    
                # El primer capítulo es el más antiguo (primer elemento del array invertido)
                first_chapter = detalles["chapters"][0]
                first_chap_date = first_chapter.get("date", "")
                
                match = re.search(r'\b(19\d{2}|20\d{2})\b', first_chap_date)
                if match:
                    first_chap_year = int(match.group(1))
                    if first_chap_year >= year_min:
                        print(f"  ✅ Encontrado: {titulo} (Año: {first_chap_year})")
                        resultados.append({
                            "id": manga_url,
                            "title": titulo,
                            "thumb": detalles.get("thumb", ""),
                            "total_chapter": detalles.get("total_chapter", 0),
                            "status": detalles.get("status", "ongoing"),
                            "type": detalles.get("type", "manga"),
                            "year": first_chap_year,
                            "summary": detalles.get("summary", "")
                        })
        except Exception as e:
            print(f"Error en buscar_por_genero_y_ano en página {page}: {e}")
            break
            
    return resultados