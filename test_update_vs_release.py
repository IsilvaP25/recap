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
    
    # Print the chapters table HTML structure or its rows
    tabla_capitulos = soup.find('div', {'class': 'chapters'})
    if tabla_capitulos:
        table = tabla_capitulos.find('table')
        if table:
            rows = table.find_all('tr')
            print(f"Total table rows: {len(rows)}")
            for idx, row in enumerate(rows):
                print(f"Row {idx+1}: {row.text.strip().replace(chr(10), ' | ')}")
        else:
            # Let's print the divs or anchor links
            print("No table inside chapters div, listing children:")
            for child in tabla_capitulos.find_all(recursive=False):
                print(f"Child tag={child.name}, class={child.get('class')}, text={child.text.strip()}")
                
            # print all rows/divs with class 'chapter'
            ch_rows = soup.select('.chapters .chapter')
            print(f"Total .chapter elements: {len(ch_rows)}")
            for idx, ch in enumerate(ch_rows):
                print(f"Chapter {idx+1}: {ch.text.strip().replace(chr(10), ' | ')}")
    else:
        print("chapters div not found")
else:
    print("Failed to fetch. Status code:", response.status_code)
