import os
import subprocess
import time
import psutil

# Datos reales
BASE_DIR = "outputs/The_Max-Level_Player_s_100th_Regression/_TEMP/Capitulo_1"
IMG_P = os.path.join(BASE_DIR, "video/temp_segments/p_00.png")
AUDIO_P = os.path.join(BASE_DIR, "audio/PAGE_01.mp3")
DUR = 28.66
OUT_P = "test_single_page.mp4"

def get_metrics():
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory().percent
    try:
        gpu_res = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'], stdout=subprocess.PIPE)
        gpu = float(gpu_res.stdout.decode().strip())
    except:
        gpu = 0
    return cpu, ram, gpu

def run_test():
    print(f"--- INICIANDO PRUEBA: 1 PÁGINA REAL ({DUR}s) ---")
    
    # Filtro actual (100% GPU con seguridad 16k)
    f_c = (f"[0:v]scale=w='if(gt(ih,16000),iw*16000/ih,iw)':h='min(ih,16000)',format=nv12,hwupload_cuda,scale_cuda=32:18[small]; [small]scale_cuda=1280:720[bg]; "
           f"[0:v]scale=w='if(gt(ih,16000),iw*16000/ih,iw)':h='min(ih,16000)',format=nv12,hwupload_cuda,scale_cuda=-2:720[fg]; "
           f"[bg][fg]overlay_cuda=x=(W-w)/2:y='if(lte(h,H), (H-h)/2, -(h-H)*(t/{DUR}))',hwdownload,format=nv12")
    
    cmd = [
        'ffmpeg', '-y', '-hwaccel', 'cuda',
        '-loop', '1', '-t', str(DUR + 0.6), '-i', IMG_P,
        '-i', AUDIO_P,
        '-filter_complex', f_c,
        '-c:v', 'h264_nvenc', '-preset', 'p1',
        '-pix_fmt', 'yuv420p', '-r', '24',
        '-c:a', 'aac', '-shortest',
        OUT_P
    ]

    start_time = time.time()
    
    # Iniciar proceso
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Monitorear recursos mientras corre
    cpu_samples = []
    gpu_samples = []
    
    while process.poll() is None:
        c, r, g = get_metrics()
        cpu_samples.append(c)
        gpu_samples.append(g)
        time.sleep(1)
        
    end_time = time.time()
    total_time = end_time - start_time
    
    avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0
    avg_gpu = sum(gpu_samples) / len(gpu_samples) if gpu_samples else 0
    
    print("\n" + "="*40)
    print("RESULTADOS DE 1 PÁGINA REAL")
    print("="*40)
    print(f"Tiempo total: {total_time:.2f} segundos")
    print(f"Duración del video: {DUR} segundos")
    print(f"Velocidad relativa: {(DUR/total_time):.2f}x")
    print(f"Uso medio CPU: {avg_cpu:.1f}%")
    print(f"Uso medio GPU: {avg_gpu:.1f}%")
    print("="*40)
    
    if os.path.exists(OUT_P): os.remove(OUT_P)

if __name__ == "__main__":
    if not os.path.exists(IMG_P) or not os.path.exists(AUDIO_P):
        print("Error: Archivos no encontrados.")
    else:
        run_test()
