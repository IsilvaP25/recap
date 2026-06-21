import os
import requests
from dotenv import load_dotenv

# Cargar configuracion
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, '.env'))

def test_manga_api():
    url = f"https://{os.getenv('RAPIDAPI_HOST')}/manga/search"
    headers = {
        "x-rapidapi-key": os.getenv("RAPIDAPI_KEY"),
        "x-rapidapi-host": os.getenv("RAPIDAPI_HOST")
    }
    params = {"text": "Solo Leveling"}
    
    print(f"Probando conexion con: {url}...")
    try:
        response = requests.get(url, headers=headers, params=params)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("data"):
                print("SUCCESS: La API respondio correctamente.")
                print(f"Mangas encontrados: {len(data['data'])}")
                print(f"Primer resultado: {data['data'][0]['title']}")
            else:
                print("WARNING: La API respondio pero no se encontraron resultados.")
        elif response.status_code == 429:
            print("ERROR: Has excedido tu cuota de RapidAPI.")
        else:
            print(f"ERROR: Fallo la API: {response.text}")
            
    except Exception as e:
        print(f"ERROR FATAL: Fallo de conexion: {str(e)}")

if __name__ == "__main__":
    test_manga_api()
