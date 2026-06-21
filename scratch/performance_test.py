import os
import subprocess
import time
import psutil
import statistics
import sys

def get_process_metrics(proc_id):
    try:
        proc = psutil.Process(proc_id)
        cpu = proc.cpu_percent(interval=0.05)
        mem = proc.memory_info().rss / (1024 * 1024) # MB
        return cpu, mem
    except:
        return 0, 0

def run_test(name, filter_complex):
    print(f"\n--- Iniciando prueba: {name} ---", flush=True)
    
    img_p = "test_img.png"
    audio_p = "test_audio.mp3"
    out_p = f"output_{name.replace(' ', '_')}.mp4"
    
    cmd = [
        'ffmpeg', '-y',
        '-loop', '1', '-t', '3', '-i', img_p, # 3 segundos
        '-i', audio_p,
        '-filter_complex', filter_complex,
        '-c:v', 'libx264', 
        '-preset', 'ultrafast',
        '-pix_fmt', 'yuv420p',
        '-r', '24',
        '-c:a', 'aac',
        '-shortest',
        out_p
    ]
    
    start_time = time.time()
    # Usamos DEVNULL para evitar bloqueos por tuberías llenas
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    cpu_usages = []
    mem_usages = []
    
    while process.poll() is None:
        cpu, mem = get_process_metrics(process.pid)
        if cpu > 0: cpu_usages.append(cpu)
        if mem > 0: mem_usages.append(mem)
        time.sleep(0.5)
    
    end_time = time.time()
    duration = end_time - start_time
    
    avg_cpu = statistics.mean(cpu_usages) if cpu_usages else 0
    max_cpu = max(cpu_usages) if cpu_usages else 0
    avg_mem = statistics.mean(mem_usages) if mem_usages else 0
    
    print(f"Resultado {name}:", flush=True)
    print(f"  Tiempo total: {duration:.2f}s", flush=True)
    print(f"  CPU Promedio: {avg_cpu:.2f}%", flush=True)
    print(f"  Memoria Promedio: {avg_mem:.2f} MB", flush=True)
    
    return {
        "duration": duration,
        "avg_cpu": avg_cpu,
        "max_cpu": max_cpu,
        "avg_mem": avg_mem
    }

if __name__ == "__main__":
    print("Preparando recursos de prueba...", flush=True)
    subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=1280x720', '-frames:v', '1', 'test_img.png'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-t', '3', 'test_audio.mp3'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    filter_blur = "[0:v]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,boxblur=5:1[bg]; [0:v]scale=-2:720[fg]; [bg][fg]overlay=(main_w-overlay_w)/2:0"
    filter_no_blur = "color=s=1280x720:c=black[bg]; [0:v]scale=-2:720[fg]; [bg][fg]overlay=(main_w-overlay_w)/2:0"
    
    res_no_blur = run_test("Sin Desenfoque (Solid)", filter_no_blur)
    res_blur = run_test("Con Desenfoque (Blur)", filter_blur)
    
    print("\n" + "="*30, flush=True)
    print("RESUMEN COMPARATIVO (3 Segundos)", flush=True)
    print("="*30, flush=True)
    
    time_diff = res_blur['duration'] - res_no_blur['duration']
    
    print(f"Ahorro de tiempo: {time_diff:.2f}s ({(time_diff/res_blur['duration'])*100:.1f}% más rápido)", flush=True)
    print(f"Carga CPU (Con Blur): {res_blur['avg_cpu']:.2f}%", flush=True)
    print(f"Carga CPU (Sin Blur): {res_no_blur['avg_cpu']:.2f}%", flush=True)
    
    for f in ["test_img.png", "test_audio.mp3", "output_Con_Desenfoque_(Blur).mp4", "output_Sin_Desenfoque_(Solid).mp4"]:
        if os.path.exists(f): 
            try: os.remove(f)
            except: pass
