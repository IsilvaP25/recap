import requests
from bs4 import BeautifulSoup

url = "https://mangakatana.com/manga"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

response = requests.get(url, headers=headers)
if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find the filter form. Usually it has checkboxes for genres.
    # Let's look for any form containing 'include_genre_chk'
    filter_form = None
    for form in soup.find_all('form'):
        if form.find('input', {'name': 'include_genre_chk'}):
            filter_form = form
            break
            
    if filter_form:
        print("Found filter form!")
        print("Action:", filter_form.get('action'))
        print("Method:", filter_form.get('method'))
        # Let's print all inputs, select, button elements in this form
        for child in filter_form.find_all(['input', 'select', 'button']):
            print(f"  Tag: {child.name}, name={child.get('name')}, type={child.get('type')}, value={child.get('value')}")
    else:
        print("Filter form not found by name 'include_genre_chk'")
        # print all forms
        for i, form in enumerate(soup.find_all('form')):
            print(f"Form {i}: action={form.get('action')}, class={form.get('class')}")
else:
    print("Failed to fetch page")
