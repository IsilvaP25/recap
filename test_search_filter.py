import requests
from bs4 import BeautifulSoup
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

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
                        
        return {
            "title": limpio,
            "chapters": lista_capitulos[::-1] # oldest to newest
        }
    except Exception as e:
        print(f"Error: {e}")
        return {}

def test_search(genre_value, year_min):
    url = f"https://mangakatana.com/manga/?filter=1&include_genre_chk={genre_value}&include_mode=and&order=latest"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    print(f"Fetching directory page for genre '{genre_value}'...")
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        uk_book = soup.find('div', {'id': 'book_list'}) or soup.find('div', {'class': 'uk-grid'})
        if uk_book:
            items = uk_book.find_all('div', {'class': 'item'})
            print(f"Found {len(items)} candidate mangas on page 1.")
            for item in items[:15]: # check first 15 to keep it fast
                t = item.find('h3', {'class': 'title'})
                if not t:
                    continue
                enlace = t.find('a')
                if not enlace:
                    continue
                
                manga_url = enlace.get('href')
                titulo = enlace.text.strip()
                
                # Get details
                detalles = obtener_detalles_completos(manga_url)
                if detalles and detalles.get("chapters"):
                    first_chapter = detalles["chapters"][0]
                    first_chap_date = first_chapter.get("date", "")
                    
                    match = re.search(r'\b(19\d{2}|20\d{2})\b', first_chap_date)
                    if match:
                        first_chap_year = int(match.group(1))
                        print(f"Manga: {titulo} | First Chapter Date: {first_chap_date} | Year: {first_chap_year}")
                        if first_chap_year >= year_min:
                            print(f"  => MATCH! {titulo} was released in {first_chap_year} (>= {year_min})")
                    else:
                        print(f"Manga: {titulo} | No year found in date: {first_chap_date}")
        else:
            print("book_list not found")
    else:
        print("Failed. Status code:", response.status_code)
 
test_search("romance", 2018)
