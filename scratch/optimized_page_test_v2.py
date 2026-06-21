import os
import subprocess
import time
import psutil

# Datos reales
BASE_DIR = "outputs/The_Max-Level_Player_s_100th_Regression/_TEMP/Capitulo_1"
IMG_P = os.path.join(BASE_DIR, "video/temp_segments/p_00.png")
AUDIO_P = os.path.join(BASE_DIR, "audio/PAGE_01.mp3")
DUR = 28.66
JPG_TEMP = "temp_optimized.jpg"
BG_TEMP = "static_bg.png"
OUT_P = "test_optimized_page_v2.mp4"

def run_optimized_test():
    print(f"--- INICIANDO PRUEBA OPTIMIZADA V2.1: 1 PÁGINA ({DUR}s) ---")
    
    # PASO 1: Preparación (Solo una vez)
    print("Preparando recursos (JPG + Fondo estático)...")
    prep_start = time.time()
    
    # 1.1 Convertir a JPG (Rápido de leer)
    subprocess.run(['ffmpeg', '-y', '-i', IMG_P, '-q:v', '4', JPG_TEMP], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 1.2 Generar el fondo borroso UNA SOLA VEZ
    # Escalamos a algo muy pequeño y luego a 720p para el efecto blur
    subprocess.run([
        'ffmpeg', '-y', '-i', JPG_TEMP, 
        '-vf', "scale=32:18,scale=1280:720", 
        '-frames:v', '1', BG_TEMP
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    prep_time = time.time() - prep_start
    print(f"Recursos listos en {prep_time:.2f}s")

    # PASO 2: Renderizado Inteligente
    # Entrada 0: El fondo estático ya borroso
    # Entrada 1: La imagen JPG original para el scroll
    # Entrada 2: El audio
    
    f_c = (f"[1:v]scale=w='if(gt(ih,16000),iw*16000/ih,iw)':h='min(ih,16000)',format=nv12,hwupload_cuda,scale_cuda=-2:720[fg]; "
           f"[0:v]format=nv12,hwupload_cuda[bg]; "
           f"[bg][fg]overlay_cuda=x=(W-w)/2:y='if(lte(h,H), (H-h)/2, -(h-H)*(t/{DUR}))',hwdownload,format=nv12")
    
    cmd = [
        'ffmpeg', '-y', '-hwaccel', 'cuda',
        '-loop', '1', '-t', str(DUR + 0.6), '-i', BG_TEMP, # Fondo estático (1 frame repetido)
        '-loop', '1', '-t', str(DUR + 0.6), '-i', JPG_TEMP, # Imagen para el scroll
        '-i', AUDIO_P,
        '-filter_complex', f_c,
        '-c:v', 'h264_nvenc', '-preset', 'p1',
        '-pix_fmt', 'yuv420p', '-r', '24',
        '-c:a', 'aac', '-shortest',
        OUT_P
    ]

    start_time = time.time()
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    render_time = time.time() - start_time
    
    total_time = render_time + prep_time
    
    print("\n" + "="*40)
    print("RESULTADOS OPTIMIZADOS (V2.1)")
    print("="*40)
    print(f"Tiempo de preparación: {prep_time:.2f}s")
    print(f"Tiempo de renderizado: {render_time:.2f}s")
    print(f"Tiempo TOTAL: {total_time:.2f} segundos")
    print(f"Velocidad relativa: {(DUR/total_time):.2f}x")
    print("="*40)
    
    # Limpieza
    for f in [JPG_TEMP, BG_TEMP, OUT_P]:
        if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    run_optimized_test()
