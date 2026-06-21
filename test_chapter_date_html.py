import requests
from bs4 import BeautifulSoup
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://mangakatana.com/manga/aishiteru-uso-dakedo.10797"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

response = requests.get(url, headers=headers)
if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')
    tabla_capitulos = soup.find('div', {'class': 'chapters'})
    if tabla_capitulos:
        table = tabla_capitulos.find('table')
        if table:
            first_row = table.find('tr')
            if first_row:
                print("--- Row HTML ---")
                print(first_row.prettify())
            else:
                print("No rows found inside table")
        else:
            print("No table found inside chapters div")
    else:
        print("chapters div not found")
else:
    print("Failed to fetch.")
