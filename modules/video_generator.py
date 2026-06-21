import os
import subprocess
import asyncio
from modules import database, utils, local_manager, audio_generator, marketing
from PIL import Image

def obtener_duracion_mp3(ruta_mp3):
    """Usa ffprobe para obtener la duracion decimal de un archivo MP3 en segundos."""
    if not os.path.exists(ruta_mp3):
        return 0.0
    comando = [
        "ffprobe", 
        "-v", "error", 
        "-show_entries", "format=duration", 
        "-of", "default=noprint_wrappers=1:nokey=1", 
        ruta_mp3
    ]
    try:
        resultado = subprocess.check_output(comando, text=True)
        return float(resultado.strip())
    except Exception as e:
        print(f"Error obteniendo duracion de {ruta_mp3}: {e}")
        return 5.0 # Duracion por defecto en caso de falla

async def generar_clip_dinamico(img_ruta, duracion, output_mp4):
    """
    Motor Híbrido Pro (V3.0): 
    - Si es Manhwa (Imagen larga): Scroll Vertical Suave.
    - Si es Manga (Imagen corta): Centrado estático con Grano.
    - Optimizado con NVENC y Pre-escalado PIL.
    """
    target_w = 720
    target_h = 1280
    
    # 1. Pre-procesar imagen con PIL para optimizar FFMPEG
    img_temp = output_mp4 + ".optimizada.jpg"
    try:
        with Image.open(img_ruta) as img:
            # Convertir a RGB si es necesario (evita problemas con RGBA en JPEG)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            w, h = img.size
            # Escalar al ancho objetivo manteniendo proporción
            new_h = int(h * (target_w / w))
            # Asegurar alto par para NVENC
            if new_h % 2 != 0: new_h -= 1
            img_res = img.resize((target_w, new_h), Image.Resampling.LANCZOS)
            img_res.save(img_temp, quality=95)
    except Exception as e:
        print(f"Error procesando imagen {img_ruta}: {e}")
        # Respaldo simple si PIL falla
        img_temp = img_ruta
        new_h = 1280 # Valor dummy

    # 2. Determinar lógica de Scroll vs Estático
    if new_h > target_h:
        # Lógica MANHWA: Scroll proporcional a la duración
        filter_complex = (
            f"pad={target_w}:ih:(ow-iw)/2:0:black,"
            f"crop={target_w}:{target_h}:0:(ih-{target_h})*(t/{duracion}),"
            f"noise=alls=5:allf=t+u" # Grano sutil
        )
    else:
        # Lógica MANGA: Centrado estático
        filter_complex = (
            f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black,"
            f"noise=alls=5:allf=t+u"
        )

    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-loop", "1", "-i", img_temp,
        "-t", str(duracion),
        "-vf", filter_complex,
        "-c:v", "h264_nvenc", "-preset", "p4", "-tune", "hq", "-pix_fmt", "yuv420p",
        "-r", "24",
        output_mp4
    ]
    
    proc = await asyncio.create_subprocess_exec(*cmd)
    await proc.communicate()
    
    # Limpiar imagen temporal
    if img_temp != img_ruta and os.path.exists(img_temp):
        try:
            os.remove(img_temp)
        except:
            pass

async def ensamblar_video_completo(m_titulo, resumen, caps, m_folder):
    """Genera la narrativa por panel de imagen, y concatena todos los capitulos en un video MP4 unico de 720p 24fps con Introduccion."""
    ruta_carpeta_video = os.path.join("Recaps", m_folder)
    os.makedirs(ruta_carpeta_video, exist_ok=True)
    
    # Preparar el directorio temporal de trabajo
    temp_dir = os.path.join(ruta_carpeta_video, "temp_render")
    os.makedirs(temp_dir, exist_ok=True)
    
    print(f"\n--- INICIANDO RENDERIZADO GLOBAL: {m_titulo} ---")
    
    # 1. Obtener la portada (usamos la primera imagen del primer capitulo)
    conn = database.conectar()
    cursor = conn.cursor()
    cursor.execute('SELECT ruta_local FROM imagenes WHERE chapter_id = ? ORDER BY id ASC LIMIT 1', (caps[0][0],))
    row = cursor.fetchone()
    conn.close()
    
    portada_img = row[0] if row else None
    if not portada_img:
        print("[!] No se encontro portada procesable.")
        return

    # 2. Renderizar Intro (Sinopsis, Titulo, Fade a Negro)
    print("Creando secuencia de intro (Sinopsis y Titulo)...")
    
    # Traducir el resumen si está en inglés (el API suele darlo en inglés)
    try:
        from deep_translator import GoogleTranslator
        resumen_es = GoogleTranslator(source='auto', target='es').translate(resumen)
        if not resumen_es: resumen_es = resumen
    except Exception as e:
        print(f"Aviso: No se pudo traducir el resumen ({e}). Usando original.")
        resumen_es = resumen

    texto_intro = f"{resumen_es}. Esta es la historia de {m_titulo}."
    intro_mp3 = os.path.join(temp_dir, "intro_audio.mp3")
    await audio_generator.generar_audio(texto_intro, intro_mp3)
    duracion_intro = obtener_duracion_mp3(intro_mp3)
    
    # Silence for the fade out and black screen (2s fade out + 3s black = 5s)
    silence_mp3 = os.path.join(temp_dir, "silence.mp3")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "5", "-c:a", "libmp3lame", silence_mp3])
    
    manifest_intro_aud = os.path.join(temp_dir, "manifest_intro_aud.txt")
    with open(manifest_intro_aud, "w", encoding="utf-8") as f:
        f.write(f"file '{os.path.abspath(intro_mp3).replace(chr(92), '/')}'\n")
        f.write(f"file '{os.path.abspath(silence_mp3).replace(chr(92), '/')}'\n")

    manifest_intro_img = os.path.join(temp_dir, "manifest_intro_img.txt")
    with open(manifest_intro_img, "w", encoding="utf-8") as f:
        f.write(f"file '{os.path.abspath(portada_img).replace(chr(92), '/')}'\n")
        f.write(f"duration {duracion_intro + 5.0}\n")
        f.write(f"file '{os.path.abspath(portada_img).replace(chr(92), '/')}'\n")

    intro_mp4 = os.path.join(temp_dir, "intro.mp4")
    cmd_intro = [
        "ffmpeg", "-y", "-v", "warning",
        "-f", "concat", "-safe", "0", "-i", manifest_intro_img,
        "-f", "concat", "-safe", "0", "-i", manifest_intro_aud,
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
        "-s", "720x1280", "-r", "24",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-vf", f"fade=t=out:st={duracion_intro}:d=2",
        "-shortest", intro_mp4
    ]
    subprocess.run(cmd_intro, check=True)
    print("- Intro generada exitosamente.")

    # 3. Procesar Capitulos individualmente para el gran concat
    print("Mapeando paneles e instanciando audio de capitulos...")
    manifest_img_path = os.path.join(temp_dir, "manifest_video.txt")
    manifest_aud_path = os.path.join(temp_dir, "manifest_audio.txt")
    videos_txt = open(manifest_img_path, "w", encoding="utf-8")
    audios_txt = open(manifest_aud_path, "w", encoding="utf-8")
    
    ultima_img_abs = None
    
    for c_id, c_titulo in caps:
        guion_text = database.obtener_guion(c_id)
        if not guion_text: continue
            
        conn = database.conectar()
        cursor = conn.cursor()
        cursor.execute('SELECT ruta_local, analisis FROM imagenes WHERE chapter_id = ? ORDER BY id ASC', (c_id,))
        filas_imgs = cursor.fetchall()
        conn.close()
        
        if not filas_imgs: continue

        # Filtrar páginas de publicidad/créditos
        imagenes_validas = []
        for ruta, analisis in filas_imgs:
            if analisis and "[CREDIT_PAGE]" in analisis:
                print(f"  - Saltando página de créditos: {os.path.basename(ruta)}")
                continue
            imagenes_validas.append(ruta)

        if not imagenes_validas: continue

        print(f"  Procesando audio y timmings de: {c_titulo}")
        
        # Generar un unico audio MASIVO por capitulo (el resumen de 10 minutos)
        mp3_capitulo = os.path.join(temp_dir, f"audio_cap_{c_id}.mp3")
        texto_limpio = guion_text.replace("*", "").replace("#", "")
        await audio_generator.generar_audio(texto_limpio, mp3_capitulo)
        
        duracion_audio = obtener_duracion_mp3(mp3_capitulo)
        if duracion_audio < 1.0: duracion_audio = 5.0
            
        # Distribuir matematicamente la duracion del gran audio entre las imagenes VALIDAS del capitulo
        cantidad_imagenes = len(imagenes_validas)
        tiempo_por_imagen = duracion_audio / cantidad_imagenes
        
        # Escribir el manifiesto del video transformando antes todo a clips dinamicos
        import sys
        print(f"    Generando {cantidad_imagenes} clips Premium (Esto tomara tiempo)... ", end="")
        sys.stdout.flush()
        
        for idx, img_ruta in enumerate(imagenes_validas):
            img_abs = os.path.abspath(img_ruta).replace("\\", "/")
            clip_name = os.path.join(temp_dir, f"clip_{c_id}_{idx}.mp4")
            
            await generar_clip_dinamico(img_abs, tiempo_por_imagen, clip_name)
            
            clip_abs = os.path.abspath(clip_name).replace("\\", "/")
            videos_txt.write(f"file '{clip_abs}'\n")
            
            # Print feedback visual rapido
            print(".", end="")
            sys.stdout.flush()
        
        print(" [OK]")
            
        # Escribir el manifiesto de audio (Un solo archivo largo que envuelve a todas esas imagenes)
        aud_abs = os.path.abspath(mp3_capitulo).replace("\\", "/")
        audios_txt.write(f"file '{aud_abs}'\n")

    videos_txt.close()
    audios_txt.close()
    
    # Renderizamos la parte de la historia (reempacando los clips Ken Burns generados)
    print("Muxing video clips y audio principal...")
    chapters_mp4 = os.path.join(temp_dir, "chapters.mp4")
    cmd_chapters = [
        "ffmpeg", "-y", "-v", "warning",
        "-f", "concat", "-safe", "0", "-i", manifest_img_path,
        "-f", "concat", "-safe", "0", "-i", manifest_aud_path,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-shortest", chapters_mp4
    ]
    subprocess.run(cmd_chapters, check=True)
    print("- Historia renderizada exitosamente.")
    
    # 4. Pegamento Final (Intro + Historia)
    print("Ensamblando render final con transiciones de corte...")
    final_mp4 = os.path.join(ruta_carpeta_video, f"Manga_Recap_Completo_{m_folder}.mp4")
    concat_list = os.path.join(temp_dir, "concat_final.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        f.write(f"file '{os.path.abspath(intro_mp4).replace(chr(92), '/')}'\n")
        f.write(f"file '{os.path.abspath(chapters_mp4).replace(chr(92), '/')}'\n")
        
    cmd_final = [
        "ffmpeg", "-y", "-v", "warning",
        "-f", "concat", "-safe", "0", "-i", concat_list,
        "-c", "copy", final_mp4
    ]
    subprocess.run(cmd_final, check=True)
    
    print(f"\n[OK] VIDEO RECAP COMPLETO EXPORTADO EXITOSAMENTE:\n => {final_mp4}")
    
    # 5. Guardado SEO Metadatos YouTube
    txt_marketing = os.path.join(ruta_carpeta_video, f"METADATOS_SEO_{m_folder}.txt")
    
    # Recolectar todo el guion para el analizador de Marketing
    guion_entero = []
    for c_id, _ in caps:
        g = database.obtener_guion(c_id)
        if g: guion_entero.append(g)
    
    if guion_entero:
        marketing.generar_metadatos_youtube(m_titulo, "\n\n".join(guion_entero), txt_marketing)
    
    # Limpiamos archivos temporales
    import shutil
    try:
        shutil.rmtree(temp_dir)
    except:
        pass
