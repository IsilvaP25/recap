import os
import subprocess
import time
import multiprocessing
import psutil
import statistics

# Rutas de archivos reales
BASE_DIR = "outputs/The_Max-Level_Player_s_100th_Regression/_TEMP/Capitulo_1"
IMG_FILES = [os.path.join(BASE_DIR, "video/temp_segments", f"p_{i:02d}.png") for i in range(4)]
AUDIO_FILES = [os.path.join(BASE_DIR, "audio", f"PAGE_{i+1:02d}.mp3") for i in range(4)]
DURATIONS = [10, 10, 10, 10] # Reducido a 10s para rapidez del test

def get_gpu_usage():
    try:
        # En Windows, nvidia-smi es la forma más fiable
        res = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'], stdout=subprocess.PIPE)
        return float(res.stdout.decode().strip())
    except:
        return 0

def render_segment(args):
    img_p, audio_p, dur, out_p = args
    # Filtro optimizado CUDA que tenemos actualmente
    f_c = (f"[0:v]scale=w='if(gt(ih,16000),iw*16000/ih,iw)':h='min(ih,16000)',format=nv12,hwupload_cuda,scale_cuda=32:18[small]; [small]scale_cuda=1280:720[bg]; "
           f"[0:v]scale=w='if(gt(ih,16000),iw*16000/ih,iw)':h='min(ih,16000)',format=nv12,hwupload_cuda,scale_cuda=-2:720[fg]; "
           f"[bg][fg]overlay_cuda=x=(W-w)/2:y=0,hwdownload,format=nv12")
    
    cmd = [
        'ffmpeg', '-y', '-hwaccel', 'cuda',
        '-loop', '1', '-t', str(dur), '-i', img_p,
        '-i', audio_p,
        '-filter_complex', f_c,
        '-c:v', 'h264_nvenc', '-preset', 'p1',
        '-pix_fmt', 'yuv420p', '-r', '24',
        '-c:a', 'aac', '-shortest',
        out_p
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def run_test_sequential():
    print("\n--- TEST: SECUENCIAL (Como está ahora) ---", flush=True)
    start_time = time.time()
    
    for i in range(4):
        render_segment((IMG_FILES[i], AUDIO_FILES[i], DURATIONS[i], f"seq_{i}.mp4"))
    
    end_time = time.time()
    return end_time - start_time

def run_test_parallel():
    print("\n--- TEST: PARALELO (Mejora propuesta) ---", flush=True)
    start_time = time.time()
    
    tasks = [(IMG_FILES[i], AUDIO_FILES[i], DURATIONS[i], f"par_{i}.mp4") for i in range(4)]
    
    # Usamos 4 procesos para las 4 páginas
    with multiprocessing.Pool(processes=4) as pool:
        pool.map(render_segment, tasks)
        
    end_time = time.time()
    return end_time - start_time

if __name__ == "__main__":
    # Verificar que existen los archivos
    for f in IMG_FILES + AUDIO_FILES:
        if not os.path.exists(f):
            print(f"Error: No se encuentra {f}")
            exit(1)

    print("Iniciando pruebas comparativas con datos REALES...")
    
    # 1. Secuencial
    t_seq = run_test_sequential()
    print(f"Tiempo Secuencial: {t_seq:.2f}s")
    
    # 2. Paralelo
    t_par = run_test_parallel()
    print(f"Tiempo Paralelo: {t_par:.2f}s")
    
    print("\n" + "="*40)
    print("RESULTADO DE LA PRUEBA")
    print("="*40)
    print(f"Ahorro de tiempo: {t_seq - t_par:.2f}s")
    print(f"Mejora de velocidad: {(t_seq / t_par):.2f}x")
    print("="*40)
    
    # Limpieza
    for i in range(4):
        for prefix in ["seq", "par"]:
            if os.path.exists(f"{prefix}_{i}.mp4"): os.remove(f"{prefix}_{i}.mp4")
