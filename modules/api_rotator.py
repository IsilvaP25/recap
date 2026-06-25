import os
import random
import json
from dotenv import load_dotenv

SESSION_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp", "exhausted_keys.json")

def _get_exhausted_keys():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def _save_exhausted_key(key):
    if not key:
        return
    try:
        os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
        exhausted = _get_exhausted_keys()
        exhausted.add(key)
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(list(exhausted), f)
    except Exception as e:
        pass

def get_all_keys(include_exhausted=False):
    """Busca todas las claves que empiecen por GEMINI_API_KEY en el .env, priorizando las gratuitas"""
    load_dotenv()
    keys = []
    
    # 1. Buscar claves numeradas a partir de la 2 (GEMINI_API_KEY_2, _3...)
    for i in range(2, 20):
        key = os.getenv(f"GEMINI_API_KEY_{i}")
        if key:
            keys.append(key)
            
    # 2. Respaldo por si se usa el nombre antiguo
    old_key = os.getenv("GEMINI_API_KEY")
    if old_key and old_key not in keys:
        keys.append(old_key)
        
    # 3. Poner la clave 1 al final (clave de pago)
    key1 = os.getenv("GEMINI_API_KEY_1")
    if key1 and key1 not in keys:
        keys.append(key1)
        
    if include_exhausted:
        return keys
        
    exhausted = _get_exhausted_keys()
    filtered_keys = [k for k in keys if k not in exhausted]
    
    # Si todas las claves están marcadas como agotadas, devolvemos la lista completa como último recurso
    if not filtered_keys:
        return keys
        
    return filtered_keys

# Índice actual para la rotación (persiste durante la ejecución del script)
_current_index = 0

def get_any_key():
    """Retorna una clave aleatoria priorizando las gratuitas y sincroniza el índice."""
    global _current_index
    keys = get_all_keys()
    if not keys:
        return None
    # Si hay más de una clave, evitamos la última (de pago) al inicio eligiendo entre las gratuitas
    if len(keys) > 1:
        _current_index = random.randint(0, len(keys) - 2)
    else:
        _current_index = 0
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
    """Lógica para informar que una clave falló y persistirla como agotada."""
    if not key: return
    _save_exhausted_key(key)

