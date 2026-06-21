import urllib.request
import json

try:
    url = "http://127.0.0.1:5000/api/library"
    print(f"Fetching: {url}")
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        data = json.loads(html)
        print(f"Status code: {response.status}")
        print(f"Data type: {type(data)}")
        print(f"Number of mangas: {len(data)}")
        if len(data) > 0:
            print("First manga record:", data[0])
except Exception as e:
    print(f"Error fetching API: {e}")
