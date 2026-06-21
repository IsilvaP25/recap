import os
from modules import api_config

def validar_acceso_gemini():
    modelos_a_probar = api_config.MODELOS_CANDIDATOS.copy()
    modelo_preferido = os.getenv("GEMINI_MODEL_ACTIVE")
    if modelo_preferido:
        if modelo_preferido in modelos_a_probar:
            modelos_a_probar.remove(modelo_preferido)
        modelos_a_probar.insert(0, modelo_preferido)
        
    keys = api_config.obtener_api_keys_disponibles()
    
    from . import utils
    h, m = utils.tiempo_hasta_reinicio_gemini()
    print(f"\n--- INICIANDO ESCANEO DE CUOTA GEMINI ({len(keys)} API Keys Detectadas) ---")
    print(f"[INFO] Proximo reinicio global de cuota diaria: en {h} horas y {m} minutos (00:00 PT).")
    
    for key_idx in range(len(keys)):
        if key_idx > 0:
            print(f"\n-> Cambiando a la API KEY #{key_idx + 1}...")
            
        client = api_config.obtener_cliente_gemini(force_new_key_index=key_idx)
        
        # Obtener lista de modelos disponibles para esta Key
        modelos_disponibles = set()
        try:
            for m in client.models.list():
                modelos_disponibles.add(m.name.replace("models/", ""))
        except Exception as e:
            print(f"[ERROR] (Key #{key_idx + 1}): Error al verificar modelos disponibles ({e}).")
            continue
            
        for modelo in modelos_a_probar:
            if modelo not in modelos_disponibles:
                print(f"[DESCARTADO] {modelo} (Key #{key_idx + 1}): Modelo no disponible en esta API Key.")
                continue
                
            try:
                client.models.generate_content(
                    model=modelo,
                    contents="ping"
                )
                print(f"[OK] {modelo} (Key #{key_idx + 1}): Tokens disponibles y activo.")
                os.environ["GEMINI_MODEL_ACTIVE"] = modelo
                return True
            except Exception as e:
                error_str = str(e)
                motivo = "Desconocido"
                
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    motivo = "Cuota agotada (Limit 0)"
                elif "404" in error_str:
                    motivo = "Modelo no encontrado"
                elif "403" in error_str:
                    motivo = "API Key invalida"
                
                print(f"[DESCARTADO] {modelo}: {motivo}")
                
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    print(f" > Cuota del modelo {modelo} agotada. Probando siguiente modelo...")
            
    print("\n[!] No se encontro ningun modelo con cuota disponible en TODAS tus API Keys.")
    return False

def obtener_estado_cuotas():
    """Retorna un diccionario con el estado de todas las llaves y modelos para la web."""
    import requests
    provider = api_config.obtener_ia_provider()
    
    estado = {
        "provider": provider,
        "gemini": [],
        "rapidapi": "Desconocido",
        "reinicio_en": ""
    }
    
    from . import utils
    h, m = utils.tiempo_hasta_reinicio_gemini()
    estado["reinicio_en"] = f"{h}h {m}m"

    # Consultar RapidAPI (Manga API)
    url = api_config.obtener_url_api("/manga")
    headers = api_config.obtener_headers()
    try:
        res = requests.get(url, headers=headers, params={"id": "659524dd597f3b00281f06ff"}, timeout=5)
        estado["rapidapi"] = res.headers.get('x-ratelimit-requests-remaining', "0")
    except:
        pass

    modelos_a_probar = api_config.MODELOS_CANDIDATOS
    keys = api_config.obtener_api_keys_disponibles()
    for i, _ in enumerate(keys):
        key_status = {"key_index": i + 1, "modelos": []}
        client = api_config.obtener_cliente_gemini(force_new_key_index=i)
        
        # Obtener lista de modelos disponibles para esta Key
        modelos_disponibles = set()
        error_listado = None
        try:
            for m in client.models.list():
                modelos_disponibles.add(m.name.replace("models/", ""))
        except Exception as e:
            error_listado = str(e)
            
        for modelo in modelos_a_probar:
            status_text = "Pendiente"
            if error_listado is not None:
                if "403" in error_listado:
                    status_text = "API Key invalida"
                else:
                    status_text = "Error listado"
            elif modelo not in modelos_disponibles:
                status_text = "No Disponible"
            else:
                try:
                    client.models.generate_content(model=modelo, contents="hi", config={"max_output_tokens": 1})
                    status_text = "Activo"
                except Exception as e:
                    err = str(e)
                    if "429" in err or "RESOURCE_EXHAUSTED" in err: 
                        status_text = "Agotado"
                    else: 
                        status_text = "Error"
            key_status["modelos"].append({"nombre": modelo, "estado": status_text})
        estado["gemini"].append(key_status)
    
    return estado

def consultar_cuota_actual():
    # ... (código existente abreviado si es necesario, pero lo mantenemos por compatibilidad con main.py)
    estado = obtener_estado_cuotas()
    print(f"RapidAPI Restantes: {estado['rapidapi']}")

def mostrar_cuota_desde_respuesta(respuesta):
    if respuesta is not None and hasattr(respuesta, 'headers'):
        remaining = respuesta.headers.get('x-ratelimit-requests-remaining')
        if remaining:
            print(f"RapidAPI Restantes: {remaining}")