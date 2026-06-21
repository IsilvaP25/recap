import os
import random
from dotenv import load_dotenv

def get_all_keys():
    """Busca todas las claves que empiecen por GEMINI_API_KEY en el .env"""
    load_dotenv()
    keys = []
    
    # 1. Buscar claves numeradas (GEMINI_API_KEY_1, _2...)
    for i in range(1, 20): # Buscamos hasta 20 claves
        key = os.getenv(f"GEMINI_API_KEY_{i}")
        if key:
            keys.append(key)
            
    # 2. Respaldo por si se usa el nombre antiguo
    old_key = os.getenv("GEMINI_API_KEY")
    if old_key and old_key not in keys:
        keys.append(old_key)
        
    return keys

# Índice actual para la rotación (persiste durante la ejecución del script)
_current_index = 0

def get_any_key():
    """Retorna una clave aleatoria del pool y sincroniza el índice."""
    global _current_index
    keys = get_all_keys()
    if not keys:
        return None
    _current_index = random.randint(0, len(keys) - 1)
    return keys[_current_index]

def get_next_key():
    """Avanza al siguiente índice de clave y lo retorna."""
    global _current_index
    keys = get_all_keys()
    if not keys:
        return None
        
    _current_index = (_current_index + 1) % len(keys)
    return keys[_current_index]

def get_current_key():
    """Retorna la clave actual sin avanzar el índice."""
    keys = get_all_keys()
    if not keys:
        return None
    return keys[_current_index % len(keys)]

def report_failed_key(key):
    """Lógica para informar que una clave falló."""
    if not key: return
    print(f"  [ROTATOR] La clave ...{key[-4:]} ha fallado o alcanzado límite. Buscando siguiente...")
