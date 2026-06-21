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
        if items:
            print("--- Printing HTML structure of first item ---")
            print(items[0].prettify()[:1500])
        else:
            print("No items found inside book_list")
    else:
        print("book_list not found")
else:
    print("Failed to fetch.")
