import requests
from bs4 import BeautifulSoup
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://mangakatana.com/manga/solo-leveling.21175/"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

response = requests.get(url, headers=headers)
if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Let's search for 4-digit numbers like 199X, 20XX
    text = soup.get_text()
    years = re.findall(r'\b(19\d{2}|20\d{2})\b', text)
    print("Found years in text:", set(years))
    
    # Let's print lines containing those years
    for line in text.split('\n'):
        if any(yr in line for yr in years):
            print("Line:", line.strip())
else:
    print("Failed to fetch.")
