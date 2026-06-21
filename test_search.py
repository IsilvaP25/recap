import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules import manga_search

results = manga_search.buscar_por_titulo("solo leveling")
for r in results:
    print({k: str(v).encode('ascii', 'ignore').decode('ascii') for k, v in r.items()})
