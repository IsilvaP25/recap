import requests
from bs4 import BeautifulSoup
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = 'https://mangakatana.com/manga'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

response = requests.get(url, headers=headers)
if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')
    uk_book = soup.find('div', {'id': 'book_list'}) or soup.find('div', {'class': 'uk-grid'})
    if uk_book:
        items = uk_book.find_all('div', {'class': 'item'})
        for idx, item in enumerate(items[:10]):
            title_tag = item.find('h3', {'class': 'title'})
            title = title_tag.text.strip() if title_tag else "No title"
            
            date_div = item.find('div', {'class': 'date'})
            date_text = date_div.text.strip() if date_div else "No date"
            
            genres = [g.text.strip() for g in item.find_all('a', href=lambda x: x and '/genre/' in x)]
            print(f"Manga {idx+1}: {title} | Date: {date_text} | Genres: {genres}")
    else:
        print("book_list not found")
else:
    print("Failed to fetch.")
