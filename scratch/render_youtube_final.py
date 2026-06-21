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
PAGE_IDX = 10 # Una página intermedia que no sea portada
OUTPUT_VIDEO = "youtube_final_preview.mp4"

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def clean_text_for_speech(text):
    # Eliminar Markdown
    text = text.replace("**", "").replace("*", "").replace("_", "").replace("#", "")
    # Eliminar corchetes y paréntesis (usualmente acotaciones)
    import re
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    return " ".join(text.split()).strip()

async def generate_youtube_preview():
    print("="*60)
    print(f"GENERANDO PREVIEW FINAL PARA YOUTUBE (Estilo Manga)")
    print("="*60)

    # --- FASE 1: PREPARACIÓN DE IMAGEN ---
    doc = fitz.open(PDF_PATH)
    page = doc.load_page(PAGE_IDX)
    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
    img_path = "temp_page_yt.png"
    pix.save(img_path)
    
    img = Image.open(img_path)
    w, h = img.size
    print(f"Imagen original: {w}x{h}")

    # --- FASE 2: VISION (IA) ---
    # Redimensionar para IA si es necesario (>16k)
    img_for_ai = img
    if h > 16000:
        scale_factor = 16000 / h
        img_for_ai = img.resize((int(w * scale_factor), 16000), Image.LANCZOS)
    
    print("[1/3] Generando guion narrativo...")
    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        prompt = "Eres un narrador de YouTube. Describe esta página de manga de forma épica para un recap. Extrae diálogos clave. Español."
        response = model.generate_content([prompt, img_for_ai])
        script_text = response.text
    except Exception as e:
        print(f"  [AVISO] Cuota agotada o error en IA: {e}")
        script_text = "El guerrero se prepara para la batalla final. El destino del mundo depende de su próximo movimiento. ¡No te pierdas este épico enfrentamiento!"
    
    print(f"Guion: {script_text[:100]}...")

    # --- FASE 3: AUDIO ---
    print("[2/3] Generando audio TTS (Voz de Álvaro)...")
    voice = "es-ES-AlvaroNeural"
    audio_path = "temp_audio_yt.mp3"
    
    texto_limpio = clean_text_for_speech(script_text)
    communicate = edge_tts.Communicate(texto_limpio, voice, rate="+25%")
    await communicate.save(audio_path)
    
    res = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path], 
                         stdout=subprocess.PIPE, text=True)
    duration = float(res.stdout.strip())
    print(f"Duración: {duration:.2f}s")

    # --- FASE 4: RENDERIZADO ESTILO YOUTUBE (1280x720) ---
    print("[3/3] Renderizando video final (1280x720 + Blur + GPU)...")
    
    # 4.1 Preparar imagen optimizada
    img_opt = "temp_img_yt_opt.jpg"
    # Escalamiento para estilo manga: Ancho fijo de 550px (proporción estándar en YouTube recaps)
    # Esto evita que los manhwas largos se vean como tiras ultra delgadas.
    subprocess.run(['ffmpeg', '-y', '-i', img_path, '-vf', "scale=550:-2:flags=lanczos,scale=h='min(ih,16384)'", '-q:v', '2', img_opt], 
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 4.2 Generar fondo borroso (1280x720) - Usamos la imagen original para que el fondo sea rico
    bg_path = "temp_bg_yt.png"
    subprocess.run(['ffmpeg', '-y', '-i', img_path, '-vf', "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,boxblur=20:10", '-frames:v', '1', bg_path],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 4.3 Comando de Renderizado Final (NVENC)
    # Detectar altura para scroll
    img_final = Image.open(img_opt)
    wf, hf = img_final.size
    y_scroll = f"if(lte(h,H),(H-h)/2,-(h-H)*(t/{duration}))"
    
    cmd = [
        'ffmpeg', '-y', '-hwaccel', 'cuda',
        '-loop', '1', '-t', str(duration), '-i', bg_path,
        '-loop', '1', '-t', str(duration), '-i', img_opt,
        '-i', audio_path,
        '-filter_complex', f"[1:v]format=nv12,hwupload_cuda[fg]; [0:v]format=nv12,hwupload_cuda[bg]; [bg][fg]overlay_cuda=x=(W-w)/2:y='{y_scroll}',hwdownload,format=nv12",
        '-c:v', 'h264_nvenc', '-preset', 'p1', '-pix_fmt', 'yuv420p', '-r', '24',
        '-c:a', 'aac', '-shortest',
        OUTPUT_VIDEO
    ]
    
    print("Iniciando renderizado de alta calidad...")
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print("\n" + "="*60)
    print(f"¡VÍDEO PARA YOUTUBE GENERADO!: {OUTPUT_VIDEO}")
    print("="*60)

    # Limpieza
    for f in [img_path, audio_path, img_opt, bg_path]:
        if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    asyncio.run(generate_youtube_preview())
