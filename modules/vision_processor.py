import os
from PIL import Image
from . import api_config, database

def preparar_instrucciones(tipo):
    instruccion_base = (
        "Describe brevemente qué está sucediendo en esta imagen y extrae el texto de los globos de diálogo. "
        "Sé extremadamente conciso. Usa un máximo de 2 o 3 oraciones. No adornes la narrativa."
    )
    if tipo == 'japan':
        return f"{instruccion_base} (Manga japonés: lee de derecha a izquierda)."
    elif tipo == 'korea' or tipo == 'china':
        return f"{instruccion_base} (Webtoon: lee de arriba hacia abajo)."
    return instruccion_base

def analizar_lote(lote_imagenes, tipo_manga):
    from . import token_monitor
    
    intentos = 0
    max_intentos = 5
    
    # Prompt optimizado para lotes
    instruccion = (
        "Analiza estas imágenes de manga/webtoon en orden secuencial.\n"
        "REGLA CRÍTICA: Si una imagen es una página de créditos, publicidad, enlaces a Discord/Patreon, "
        "o portadas de grupos de traducción (que no son parte de la historia), "
        "ENTONCES responde exclusivamente 'Página X: [CREDIT_PAGE]' para esa página.\n"
        "Para las páginas de la historia: proporciona una descripción breve (2-3 oraciones) de lo que sucede y los diálogos clave. "
        "Usa el formato: 'Página X: [descripción]'. "
    )
    if tipo_manga == 'japan':
        instruccion += "(Manga japonés: lee de derecha a izquierda)."
    elif tipo_manga in ['korea', 'china']:
        instruccion += "(Webtoon: lee de arriba hacia abajo)."

    provider = api_config.obtener_ia_provider()
    
    while intentos < max_intentos:
        modelo = api_config.nombre_modelo_vision()
        
        try:
            client = api_config.obtener_cliente_gemini()
            # Preparamos el contenido multimodal: instrucciones + lista de imágenes PIL
            contenidos = [instruccion]
            for ruta in lote_imagenes:
                img = Image.open(ruta)
                contenidos.append(img)
            
            response = client.models.generate_content(
                model=modelo,
                contents=contenidos
            )
            return response.text
                
        except Exception as e:
            error_str = str(e)
            if provider == "gemini" and ("429" in error_str or "RESOURCE_EXHAUSTED" in error_str):
                print(f"[!] Cuota agotada en {modelo}. Escaneando otras llaves...")
                try:
                    from modules import api_rotator
                    keys_list = api_config.obtener_api_keys_disponibles()
                    curr_idx = api_config.get_current_key_index()
                    if curr_idx < len(keys_list):
                        api_rotator.report_failed_key(keys_list[curr_idx])
                except Exception:
                    pass
                if token_monitor.validar_acceso_gemini():
                    intentos += 1
                    import time
                    time.sleep(1)
                    continue
                else:
                    return "FATAL_QUOTA_ERROR: No hay más cuotas disponibles en ninguna API Key."
            else:
                return f"Error en {modelo} ({provider}): {e}"
                
    return "Error: Máximo de reintentos alcanzado en el lote."

def generar_guion_capitulo(chapter_id, info_progreso=""):
    conn = database.conectar()
    cursor = conn.cursor()
    # Ahora pedimos tambien el id de la imagen y el analisis previo
    cursor.execute('''
        SELECT i.id, i.ruta_local, m.tipo, m.titulo, i.analisis
        FROM imagenes i
        JOIN capitulos c ON i.chapter_id = c.id
        JOIN mangas m ON c.manga_id = m.id
        WHERE i.chapter_id = ?
        ORDER BY i.id ASC
    ''', (chapter_id,))
    filas = cursor.fetchall()
    conn.close()
    
    if not filas: return "No hay imagenes."
    
    tipo_manga = filas[0][2]
    m_titulo = filas[0][3]
    narracion_cruda: list[str] = []
    
    # Procesamiento por lotes de 10
    batch_size = 10
    total_imgs = len(filas)
    
    from modules import utils
    indices_lotes = list(range(0, total_imgs, batch_size))
    
    for i in utils.barra_progreso(indices_lotes, prefijo=f'{info_progreso} Lotes:', longitud=30):
        lote_filas = filas[i : i + batch_size]
        
        # Filtrar imágenes que ya tienen análisis (RESUME FEATURE)
        lote_a_procesar = []
        lote_rutas = []
        for f_id, f_ruta, f_tipo, f_titulo, f_analisis in lote_filas:
            if f_analisis and len(f_analisis.strip()) > 10:
                narracion_cruda.append(f_analisis)
            else:
                if os.path.exists(f_ruta):
                    lote_a_procesar.append(f_id)
                    lote_rutas.append(f_ruta)
        
        if lote_rutas:
            # print(f" > Procesando lote {i//batch_size + 1} ({len(lote_rutas)} imágenes nuevas)...") # Comentado para no ensuciar la barra
            resultado_lote = analizar_lote(lote_rutas, tipo_manga)
            
            if "FATAL_QUOTA_ERROR" in resultado_lote:
                print(f"\n[!] Deteniendo: {resultado_lote}")
                return resultado_lote

            # Guardamos el resultado del lote
            for img_id in lote_a_procesar:
                database.guardar_analisis_imagen(img_id, resultado_lote)
            
            narracion_cruda.append(resultado_lote)
        # else:
            # print(f" > Lote {i//batch_size + 1} ya analizado. Recuperando de DB.")

    # Filtrar lineas de credito antes de compilar para el resumen final
    lineas_limpias = []
    for bloque in narracion_cruda:
        for linea in bloque.split("\n"):
            if "[CREDIT_PAGE]" not in linea:
                lineas_limpias.append(linea)
    
    texto_compilado = "\n".join(lineas_limpias)
    
    # FASE 2: Resumen del Capitulo
    print("\n[!] Fase 1 completada. Generando guion narrativo final (Objetivo: 1100-1400 palabras)...")
    prompt_resumen = (
        "Eres un experto guionista de resúmenes de Manga/Anime para YouTube. "
        "A continuación te proporciono una lista de eventos y diálogos que ocurren en un capítulo "
        "extraídos de sus imágenes crudas.\n\n"
        "TU TAREA:\n"
        "Escribe un guión narrativo épico, fluido y continuo basado en estos eventos que será leído por un actor de doblaje (TTS). "
        "REGLA DE ORO: Tu guion DEBE tener rigurosamente entre 1100 y 1400 palabras de longitud para asegurar un tiempo de video de 8 a 10 minutos. "
        "No incluyas acotaciones de escena, nombres sueltos antes de hablar, ni introducciones robóticas. "
        "Solo devuelve el texto del guión listo para ser narrado, sin etiquetas ni formato especial.\n\n"
        f"--- INICIO DE LOS EVENTOS DEL CAPITULO ---\n{texto_compilado}\n--- FIN DE LOS EVENTOS ---"
    )
    
    import time
    from . import token_monitor
    
    intentos = 0
    provider = api_config.obtener_ia_provider()
    while intentos < 5:
        modelo = api_config.nombre_modelo_ia()
        try:
            client = api_config.obtener_cliente_gemini()
            response = client.models.generate_content(
                model=modelo,
                contents=prompt_resumen
            )
            print(f"[+] Guion final generado con Gemini ({modelo}).")
            return response.text
        except Exception as e:
            error_str = str(e)
            if provider == "gemini" and ("429" in error_str or "RESOURCE_EXHAUSTED" in error_str):
                print(f"[!] Cuota agotada en {modelo} durante el resumen final. Buscando proxima key...")
                try:
                    from modules import api_rotator
                    keys_list = api_config.obtener_api_keys_disponibles()
                    curr_idx = api_config.get_current_key_index()
                    if curr_idx < len(keys_list):
                        api_rotator.report_failed_key(keys_list[curr_idx])
                except Exception:
                    pass
                if token_monitor.validar_acceso_gemini():
                    intentos += 1
                    import time
                    time.sleep(1)
                    continue
                else:
                    return "FATAL_QUOTA_ERROR: No hay más cuotas para el resumen final."
            else:
                 return f"Error en generacion de resumen ({provider}): {e}"
                 
    return "Error por demasiados reintentos en el resumen."