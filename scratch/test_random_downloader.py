import os
import sys
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from modules import database
from modules.flows import downloader_flow

def main():
    database.inicializar_db()
    
    print("Iniciando prueba automatizada de la opción 6...")
    print("Mockeando input del año para que devuelva 2018 y descargar 2 mangas...")
    
    with patch('builtins.input', return_value="2018"):
        downloader_flow.descargar_capitulo_uno_filtrados(2)

if __name__ == "__main__":
    main()
