import os
from dotenv import load_dotenv
from google import genai

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, '.env'))

MODELOS_CANDIDATOS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro",
    "gemini-pro"
]

def obtener_ia_provider():
    """Retorna el proveedor configurado: 'gemini'."""
    return os.getenv("AI_PROVIDER", "gemini").lower()

def nombre_modelo_ia():
    """Modelo para generacion de guiones creativos."""
    return os.getenv("GEMINI_MODEL_ACTIVE", "gemini-2.0-flash")

def nombre_modelo_vision():
    """Modelo ultra-eficiente para analisis masivo de imagenes."""
    return os.getenv("GEMINI_MODEL_VISION", "gemini-1.5-flash-8b")

def obtener_headers():
    return {
        "x-rapidapi-key": os.getenv("RAPIDAPI_KEY"),
        "x-rapidapi-host": os.getenv("RAPIDAPI_HOST")
    }

def obtener_url_api(endpoint):
    host = os.getenv("RAPIDAPI_HOST")
    return f"https://{host}{endpoint}"

_gemini_client = None
_current_api_key_index = 0
_current_api_key_value = None

def obtener_api_keys_disponibles():
    """Busca todas las variables GEMINI_API_KEY, GEMINI_API_KEY_1, GEMINI_API_KEY_2..."""
    keys = []
    
    # 1. Buscar claves numeradas (GEMINI_API_KEY_1, _2...)
    for i in range(1, 20):
        kx = os.getenv(f"GEMINI_API_KEY_{i}")
        if kx and kx not in keys:
            keys.append(kx)
            
    # 2. Respaldo por si se usa el nombre sin número
    old_key = os.getenv("GEMINI_API_KEY")
    if old_key and old_key not in keys:
        keys.append(old_key)
        
    return keys

def obtener_cliente_gemini(force_new_key_index=None):
    global _gemini_client
    global _current_api_key_index
    global _current_api_key_value
    
    keys = obtener_api_keys_disponibles()
    if not keys:
        raise ValueError("No se encontro ninguna GEMINI_API_KEY.")

    if force_new_key_index is not None:
        _current_api_key_index = force_new_key_index
        _gemini_client = None
        
    if _current_api_key_index >= len(keys):
        _current_api_key_index = 0

    api_key = keys[_current_api_key_index]

    if _gemini_client is None or _current_api_key_value != api_key:
        if "GOOGLE_API_KEY" in os.environ:
            del os.environ["GOOGLE_API_KEY"]
        _gemini_client = genai.Client(api_key=api_key)
        _current_api_key_value = api_key
        
    return _gemini_client
    
def get_current_key_index():
    return _current_api_key_index

def obtener_capitulos_por_parte():
    """Retorna el número de capítulos por parte configurado en el .env, por defecto 7."""
    try:
        return int(os.getenv("CHAPTERS_PER_PART", 7))
    except (ValueError, TypeError):
        return 7