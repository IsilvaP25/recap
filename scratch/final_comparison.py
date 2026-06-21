import os
import subprocess
import time
import psutil
import statistics

def get_process_metrics(proc_id):
    try:
        proc = psutil.Process(proc_id)
        # Tomamos una muestra de CPU (0.1s)
        cpu = proc.cpu_percent(interval=0.1)
        return cpu
    except:
        return 0

def run_test(name, cmd):
    print(f"\n--- Iniciando: {name} ---", flush=True)
    
    start_time = time.time()
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    cpu_samples = []
    while process.poll() is None:
        cpu = get_process_metrics(process.pid)
        if cpu > 0: cpu_samples.append(cpu)
        time.sleep(0.4)
    
    end_time = time.time()
    duration = end_time - start_time
    avg_cpu = statistics.mean(cpu_samples) if cpu_samples else 0
    
    print(f"  Completado en {duration:.2f}s | CPU Avg: {avg_cpu:.2f}%", flush=True)
    return {"time": duration, "cpu": avg_cpu}

if __name__ == "__main__":
    # Preparar archivos
    subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=1280x720', '-frames:v', '1', 'test_img.png'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-t', '5', 'test_audio.mp3'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    results = {}
    
    # --- PRUEBAS CPU (libx264) ---
    cmd_base_cpu = ['ffmpeg', '-y', '-loop', '1', '-t', '5', '-i', 'test_img.png', '-i', 'test_audio.mp3', '-c:v', 'libx264', '-preset', 'ultrafast', '-r', '24', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest']
    
    # 1. CPU SIN BLUR
    f_cpu_no = "[0:v]scale=1280:720[bg]; [0:v]scale=-2:720[fg]; [bg][fg]overlay=(W-w)/2:0"
    results["CPU - SIN Desenfoque"] = run_test("CPU - SIN Desenfoque", cmd_base_cpu + ['-filter_complex', f_cpu_no, 'out_cpu_no.mp4'])
    
    # 2. CPU CON BLUR
    f_cpu_yes = "[0:v]scale=1280:720,boxblur=5:1[bg]; [0:v]scale=-2:720[fg]; [bg][fg]overlay=(W-w)/2:0"
    results["CPU - CON Desenfoque"] = run_test("CPU - CON Desenfoque", cmd_base_cpu + ['-filter_complex', f_cpu_yes, 'out_cpu_yes.mp4'])
    
    # --- PRUEBAS GPU (h264_nvenc + CUDA) ---
    cmd_base_gpu = ['ffmpeg', '-y', '-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda', '-loop', '1', '-t', '5', '-i', 'test_img.png', '-i', 'test_audio.mp3', '-c:v', 'h264_nvenc', '-preset', 'p1', '-r', '24', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest']
    
    # 3. GPU SIN BLUR
    f_gpu_no = "[0:v]scale_cuda=1280:720[bg]; [0:v]scale_cuda=-2:720[fg]; [bg][fg]overlay_cuda=x=(W-w)/2:y=0"
    results["GPU - SIN Desenfoque"] = run_test("GPU - SIN Desenfoque", cmd_base_gpu + ['-filter_complex', f_gpu_no, 'out_gpu_no.mp4'])
    
    # 4. GPU CON BLUR (Scale-Blur Trick)
    f_gpu_yes = "[0:v]scale_cuda=32:18[small]; [small]scale_cuda=1280:720[bg]; [0:v]scale_cuda=-2:720[fg]; [bg][fg]overlay_cuda=x=(W-w)/2:y=0"
    results["GPU - CON Desenfoque"] = run_test("GPU - CON Desenfoque", cmd_base_gpu + ['-filter_complex', f_gpu_yes, 'out_gpu_yes.mp4'])
    
    # --- TABLA FINAL ---
    print("\n" + "="*60)
    print(f"{'ESCENARIO':<30} | {'TIEMPO':<10} | {'CPU AVG':<10}")
    print("-" * 60)
    for name, res in results.items():
        print(f"{name:<30} | {res['time']:>8.2f}s | {res['cpu']:>8.2f}%")
    print("="*60)
    
    # Limpieza
    for f in ["test_img.png", "test_audio.mp3", "out_cpu_no.mp4", "out_cpu_yes.mp4", "out_gpu_no.mp4", "out_gpu_yes.mp4"]:
        if os.path.exists(f): os.remove(f)
