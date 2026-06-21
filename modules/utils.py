import sys

def sanitizar_nombre_carpeta(nombre):
    """Limpia un nombre para que sea seguro usarlo como carpeta, eliminando comas y caracteres especiales."""
    return "".join([c if c.isalnum() or c in (' ', '-', '_') else '_' for c in nombre]).replace(" ", "_")

def barra_progreso(iterable, prefijo='', sufijo='', decimales=2, longitud=5):
    import os, sys
    if os.name == 'nt': os.system('') # Activa soporte ANSI en Windows
    
    total = len(iterable)
    # Prefijo ultra corto (solo los primeros 15 caracteres)
    prefijo_corto = prefijo[:15]
    
    def print_barra(iteracion):
        porcentaje = ("{0:." + str(decimales) + "f}").format(100 * (iteracion / float(total)))
        # Barra mini de 5 bloques
        llenado = int(longitud * iteracion // total)
        barra = '#' * llenado + '-' * (longitud - llenado)
        
        # Linea definitiva: [Texto] |###--| 50%
        # \r al inicio, \x1b[K limpia hasta el final de la linea
        linea = f"\r\x1b[K{prefijo_corto} |{barra}| {porcentaje}%"
        sys.stdout.write(linea)
        sys.stdout.flush()
    
    print_barra(0)
    for i, item in enumerate(iterable):
        yield item
        print_barra(i + 1)
    sys.stdout.write('\n')

def tiempo_hasta_reinicio_gemini():
    """Calcula el tiempo restante hasta las 00:00 PT (Pacific Time)."""
    import datetime
    import zoneinfo
    
    try:
        # Intentar usar zona horaria de EE.UU./Pacífico
        tz_pt = zoneinfo.ZoneInfo("America/Los_Angeles")
    except:
        # Fallback si no está instalada la base de datos de zonas (usar offset manual aproximado UTC-7/8)
        # Para simplificar, asumiremos UTC-7 (PDT)
        tz_pt = datetime.timezone(datetime.timedelta(hours=-7))

    ahora_pt = datetime.datetime.now(tz_pt)
    manana_pt = (ahora_pt + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    restante = manana_pt - ahora_pt
    horas, rem = divmod(restante.seconds, 3600)
    minutos, _ = divmod(rem, 60)
    
    return horas, minutos

def limpiar_archivos_intermedios(manga_name, chunk):
    """
    Elimina audios, videos y guiones traducidos que no son necesarios
    tras la consolidación, ahorrando espacio. Solo se conserva el guion en inglés.
    """
    import os
    import shutil
    print(f"\n  [CLEANUP] Iniciando limpieza de activos intermedios para {manga_name}...")
    
    def format_cap(num):
        try:
            val = float(num)
            return str(int(val)) if val == int(val) else str(val)
        except (ValueError, TypeError):
            return str(num)
            
    # Intentar detectar la ruta base (asumiendo que estamos en modules/)
    base_proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manga_dir = os.path.join(base_proj, "outputs", manga_name)
    
    for cap_raw in chunk:
        cap = format_cap(cap_raw)
        # 1. Audios individuales
        audio_p = os.path.join(manga_dir, "AUDIOS", f"Capitulo_{cap}_ESP.mp3")
        if os.path.exists(audio_p): os.remove(audio_p)
            
        # 2. Videos individuales
        video_p = os.path.join(manga_dir, "VIDEOS", f"Capitulo_{cap}.mp4")
        if os.path.exists(video_p): os.remove(video_p)
            
        # 3. Guiones en Español
        script_esp_p = os.path.join(manga_dir, "Scripts", f"Capitulo_{cap}_guion_ESP.txt")
        if os.path.exists(script_esp_p): os.remove(script_esp_p)
            
        # 4. Metadatos (ya consolidados en FINAL_PUBLICATION)
        meta_p = os.path.join(manga_dir, "Scripts", f"Capitulo_{cap}_metadata.json")
        if os.path.exists(meta_p): os.remove(meta_p)
        
        # 5. Carpeta temporal de frames
        temp_dir = os.path.join(manga_dir, "_TEMP", f"Capitulo_{cap}")
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)

    # Se conservan los archivos del Short por solicitud de independencia en el flujo
            
    # Las miniaturas se conservan por precaución según solicitud del usuario
    # start_c, end_c = chunk[0], chunk[-1]
    # thumb_p = os.path.join(manga_dir, "MINIATURAS", f"MegaRecap_{start_c}_al_{end_c}.png")
    # if os.path.exists(thumb_p): os.remove(thumb_p)
    
    print(f"  [OK] Limpieza completada. Se conservan guiones RAW, miniaturas y el MegaRecap final.")
