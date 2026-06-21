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
OUT_P = "test_optimized_page.mp4"

def get_metrics():
    cpu = psutil.cpu_percent(interval=None)
    try:
        gpu_res = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'], stdout=subprocess.PIPE)
        gpu = float(gpu_res.stdout.decode().strip())
    except:
        gpu = 0
    return cpu, gpu

def run_optimized_test():
    print(f"--- INICIANDO PRUEBA OPTIMIZADA: 1 PÁGINA ({DUR}s) ---")
    
    # PASO 1: Conversión única PNG -> JPG (con ajuste de tamaño para GPU)
    print("Optimizando imagen para GPU (paso único)...")
    prep_start = time.time()
    # Usamos ffmpeg para convertir a JPG de alta calidad y limitar a 16k de alto
    conv_cmd = [
        'ffmpeg', '-y', '-i', IMG_P,
        '-vf', "scale=w='if(gt(ih,16384),iw*16384/ih,iw)':h='min(ih,16384)'",
        '-q:v', '2', JPG_TEMP
    ]
    subprocess.run(conv_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    prep_time = time.time() - prep_start
    print(f"Imagen preparada en {prep_time:.2f}s")

    # PASO 2: Renderizado 100% Hardware
    # Usamos mjpeg_cuvid para decodificar la imagen en la GPU
    f_c = (f"[0:v]scale_cuda=32:18[small]; [small]scale_cuda=1280:720[bg]; "
           f"[0:v]scale_cuda=-2:720[fg]; "
           f"[bg][fg]overlay_cuda=x=(W-w)/2:y='if(lte(h,H), (H-h)/2, -(h-H)*(t/{DUR}))',hwdownload,format=nv12")
    
    cmd = [
        'ffmpeg', '-y', 
        '-hwaccel', 'cuda', 
        '-hwaccel_output_format', 'cuda',
        '-c:v', 'mjpeg_cuvid', # DECODIFICADOR HARDWARE
        '-loop', '1', '-t', str(DUR + 0.6), '-i', JPG_TEMP,
        '-i', AUDIO_P,
        '-filter_complex', f_c,
        '-c:v', 'h264_nvenc', '-preset', 'p1',
        '-pix_fmt', 'yuv420p', '-r', '24',
        '-c:a', 'aac', '-shortest',
        OUT_P
    ]

    start_time = time.time()
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    cpu_samples = []
    gpu_samples = []
    
    while process.poll() is None:
        c, g = get_metrics()
        cpu_samples.append(c)
        gpu_samples.append(g)
        time.sleep(1)
        
    render_time = time.time() - start_time
    total_time = render_time + prep_time
    
    avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0
    avg_gpu = sum(gpu_samples) / len(gpu_samples) if gpu_samples else 0
    
    print("\n" + "="*40)
    print("RESULTADOS OPTIMIZADOS (V2.0)")
    print("="*40)
    print(f"Tiempo de preparación: {prep_time:.2f}s")
    print(f"Tiempo de renderizado: {render_time:.2f}s")
    print(f"Tiempo TOTAL: {total_time:.2f} segundos")
    print(f"Velocidad relativa: {(DUR/total_time):.2f}x")
    print(f"Uso medio CPU: {avg_cpu:.1f}%")
    print(f"Uso medio GPU: {avg_gpu:.1f}%")
    print("="*40)
    
    # Limpieza
    if os.path.exists(OUT_P): os.remove(OUT_P)
    if os.path.exists(JPG_TEMP): os.remove(JPG_TEMP)

if __name__ == "__main__":
    run_optimized_test()
