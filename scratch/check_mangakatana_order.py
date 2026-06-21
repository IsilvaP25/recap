import requests
from bs4 import BeautifulSoup

urls = {
    "filter_latest_p100": "https://mangakatana.com/manga/page/100?filter=1&order=latest",
    "filter_hot_p100": "https://mangakatana.com/manga/page/100?filter=1&order=hot",
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

for name, url in urls.items():
    print(f"\n--- URL: {name} ({url}) ---")
    try:
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            print(f"Status code: {r.status_code}")
            continue
        soup = BeautifulSoup(r.text, 'html.parser')
        uk_book = soup.find('div', {'id': 'book_list'}) or soup.find('div', {'class': 'uk-grid'})
        if not uk_book:
            print("Book list not found")
            continue
        titulos = uk_book.find_all('h3', {'class': 'title'})
        for i, t in enumerate(titulos[:5]):
            print(f"  {i+1}. {t.text.strip()}")
    except Exception as e:
        print(f"Error: {e}")
