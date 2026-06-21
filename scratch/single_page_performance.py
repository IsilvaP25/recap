import os
import time
import psutil
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

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_metrics():
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory().percent
    try:
        gpu_res = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'], 
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        gpu = float(gpu_res.stdout.decode().strip())
    except:
        gpu = 0
    return cpu, ram, gpu

async def run_performance_test():
    stats = {"vision": [], "audio": [], "video": []}
    times = {}
    
    print("="*60)
    print(f"INICIANDO TEST DE RENDIMIENTO: 1 PÁGINA REAL")
    print("="*60)

    # --- FASE 1: VISION (IA) ---
    print("\n[1/3] FASE VISION: Generando guion con Gemini...")
    start_v = time.time()
    doc = fitz.open(PDF_PATH)
    page = doc.load_page(PAGE_IDX)
    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    prompt = "Describe briefly what is happening and extract dialogue. Be concise. Spanish."
    
    # Monitoreo Vision
    v_stats = []
    
    # Nota: No podemos monitorear fácilmente mientras esperamos el await de la API 
    # sin hilos, pero haremos un muestreo simple.
    response = model.generate_content([prompt, img])
    script_text = response.text
    
    times['vision'] = time.time() - start_v
    print(f"  Guion generado en {times['vision']:.2f}s")
    print(f"  Texto: {script_text[:100]}...")

    # --- FASE 2: AUDIO (TTS) ---
    print("\n[2/3] FASE AUDIO: Generando TTS con Edge-TTS...")
    start_a = time.time()
    voice = "es-ES-AlvaroNeural"
    audio_path = "performance_temp.mp3"
    
    communicate = edge_tts.Communicate(script_text, voice, rate="+25%")
    await communicate.save(audio_path)
    
    # Obtener duración del audio
    cmd_dur = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
    res_dur = subprocess.run(cmd_dur, stdout=subprocess.PIPE, text=True)
    audio_duration = float(res_dur.stdout.strip())
    
    times['audio'] = time.time() - start_a
    print(f"  Audio generado en {times['audio']:.2f}s (Duración: {audio_duration:.2f}s)")

    # --- FASE 3: VIDEO (RENDERIZADO OPTIMIZADO) ---
    print("\n[3/3] FASE VIDEO: Renderizando con GPU (NVENC + Optimized Logic)...")
    img_path = "performance_temp.png"
    pix.save(img_path)
    output_video = "performance_test_result.mp4"
    
    # Lógica optimizada: Pre-escalado y renderizado directo
    start_vid = time.time()
    
    # 3.1 Pre-escalado (Paso rápido)
    img_opt = "performance_opt.jpg"
    # Escalamos al ancho de 1280 (720p) y limitamos a 16k
    subprocess.run(['ffmpeg', '-y', '-i', img_path, '-vf', "scale=1280:-2:flags=lanczos,scale=h='min(ih,16384)'", '-q:v', '2', img_opt], 
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 3.2 Renderizado Final
    # Usamos overlay con scroll si es larga
    w_opt, h_opt = Image.open(img_opt).size
    is_long = h_opt > 720
    
    if is_long:
        f_c = (f"[0:v]scale=32:18,scale=1280:720,boxblur=20:10[bg]; "
               f"[bg][0:v]overlay=x=(W-w)/2:y='-(h-H)*(t/{audio_duration})'")
    else:
        f_c = (f"[0:v]scale=32:18,scale=1280:720,boxblur=20:10[bg]; "
               f"[bg][0:v]overlay=x=(W-w)/2:y=(H-h)/2")

    cmd_render = [
        'ffmpeg', '-y', '-hwaccel', 'cuda',
        '-loop', '1', '-t', str(audio_duration), '-i', img_opt,
        '-i', audio_path,
        '-filter_complex', f_c,
        '-c:v', 'h264_nvenc', '-preset', 'p1', '-pix_fmt', 'yuv420p', '-r', '24',
        '-c:a', 'aac', '-shortest',
        output_video
    ]
    
    cpu_samples = []
    gpu_samples = []
    
    render_proc = subprocess.Popen(cmd_render, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    while render_proc.poll() is None:
        c, r, g = get_metrics()
        cpu_samples.append(c)
        gpu_samples.append(g)
        time.sleep(0.5)
        
    times['video'] = time.time() - start_vid
    avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0
    avg_gpu = sum(gpu_samples) / len(gpu_samples) if gpu_samples else 0
    
    print(f"  Video renderizado en {times['video']:.2f}s")
    
    # RESUMEN
    print("\n" + "="*60)
    print("RESULTADOS FINALES")
    print("="*60)
    print(f"{'FASE':<15} | {'TIEMPO':<10} | {'RENDIMIENTO'}")
    print("-" * 60)
    print(f"{'Vision (IA)':<15} | {times['vision']:>7.2f}s | N/A")
    print(f"{'Audio (TTS)':<15} | {times['audio']:>7.2f}s | N/A")
    print(f"{'Video (GPU)':<15} | {times['video']:>7.2f}s | CPU: {avg_cpu:.1f}% / GPU: {avg_gpu:.1f}%")
    print("-" * 60)
    total = sum(times.values())
    print(f"{'TOTAL':<15} | {total:>7.2f}s | Eficiencia: {(audio_duration/times['video']):.2f}x (Video)")
    print("="*60)

    # Limpieza
    for f in [audio_path, img_path, img_opt, output_video]:
        if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    asyncio.run(run_performance_test())
