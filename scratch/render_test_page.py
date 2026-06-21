import os
import time
import subprocess
import asyncio
import io
import fitz
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import edge_tts

# CONFIG
MANGA_NAME = "The_Max-Level_Player_s_100th_Regression"
PDF_PATH = r"pdf_storage\The_Max-Level_Player_s_100th_Regression\Capitulo_1.pdf"
PAGE_IDX = 0 # Página 1
OUTPUT_VIDEO = "test_page_output.mp4"

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

async def generate_test_video():
    print("="*60)
    print(f"GENERANDO VIDEO DE PRUEBA: PÁGINA 1 (Optimizado)")
    print("="*60)

    # --- FASE 1: PREPARACIÓN DE IMAGEN ---
    doc = fitz.open(PDF_PATH)
    page = doc.load_page(PAGE_IDX)
    # Extraemos en alta calidad para el video
    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
    img_path = "temp_page.png"
    pix.save(img_path)
    
    img = Image.open(img_path)
    w, h = img.size
    print(f"Dimensiones originales: {w}x{h}")

    # --- FASE 2: VISION (IA) ---
    # SOLUCIÓN AL ERROR 16K: Re-escalar solo para la IA si es necesario
    img_for_ai = img
    if h > 16000:
        print(f"Redimensionando imagen para IA (Límite WebP)...")
        scale_factor = 16000 / h
        img_for_ai = img.resize((int(w * scale_factor), 16000), Image.LANCZOS)
    
    print("[1/3] Obteniendo guion de Gemini...")
    model = genai.GenerativeModel('gemini-flash-latest')
    prompt = "Describe brevemente qué sucede y extrae los diálogos. En español."
    response = model.generate_content([prompt, img_for_ai])
    script_text = response.text
    print(f"Guion: {script_text[:100]}...")

    # --- FASE 3: AUDIO ---
    print("[2/3] Generando audio TTS...")
    voice = "es-ES-AlvaroNeural"
    audio_path = "temp_audio.mp3"
    communicate = edge_tts.Communicate(script_text, voice, rate="+25%")
    await communicate.save(audio_path)
    
    # Obtener duración
    res = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path], 
                         stdout=subprocess.PIPE, text=True)
    duration = float(res.stdout.strip())
    print(f"Duración: {duration:.2f}s")

    # --- FASE 4: VIDEO RENDER (OPTIMIZADO) ---
    print("[3/3] Renderizando video con scroll fluido...")
    
    # 4.1 Preparar imagen optimizada para GPU
    img_opt = "temp_img_opt.jpg"
    # Escalamos al ancho de 1280 (720p) para que el scroll sea suave y quepa en la GPU
    subprocess.run(['ffmpeg', '-y', '-i', img_path, '-vf', "scale=1280:-2:flags=lanczos,scale=h='min(ih,16384)'", '-q:v', '2', img_opt], 
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 4.2 Render con fondo desenfocado
    # Generamos el fondo una sola vez
    bg_path = "temp_bg.png"
    subprocess.run(['ffmpeg', '-y', '-i', img_opt, '-vf', "scale=32:18,scale=1280:720,boxblur=20:10", '-frames:v', '1', bg_path],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Obtener nueva altura de la imagen optimizada
    img_final = Image.open(img_opt)
    wf, hf = img_final.size
    
    # Si la imagen sigue siendo más alta que el video (720), hacemos scroll
    if hf > 720:
        y_filter = f"'-(h-H)*(t/{duration})'"
    else:
        y_filter = "(H-h)/2"

    cmd = [
        'ffmpeg', '-y', '-hwaccel', 'cuda',
        '-loop', '1', '-t', str(duration), '-i', bg_path,
        '-loop', '1', '-t', str(duration), '-i', img_opt,
        '-i', audio_path,
        '-filter_complex', f"[1:v]format=nv12,hwupload_cuda[fg]; [0:v]format=nv12,hwupload_cuda[bg]; [bg][fg]overlay_cuda=x=(W-w)/2:y={y_filter},hwdownload,format=nv12",
        '-c:v', 'h264_nvenc', '-preset', 'p1', '-pix_fmt', 'yuv420p', '-r', '24',
        '-c:a', 'aac', '-shortest',
        OUTPUT_VIDEO
    ]
    
    print("Ejecutando FFmpeg NVENC...")
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print("\n" + "="*60)
    print(f"¡EXITO! Video generado: {OUTPUT_VIDEO}")
    print("="*60)

    # Limpieza parcial (dejamos el video)
    for f in [img_path, audio_path, img_opt, bg_path]:
        if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    asyncio.run(generate_test_video())
