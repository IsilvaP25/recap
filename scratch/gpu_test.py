import os
import subprocess
import time
import psutil
import statistics

def get_process_metrics(proc_id):
    try:
        proc = psutil.Process(proc_id)
        cpu = proc.cpu_percent(interval=0.1)
        mem = proc.memory_info().rss / (1024 * 1024)
        return cpu, mem
    except:
        return 0, 0

def run_test(name, filter_complex, hw_args=[]):
    print(f"\n--- Iniciando prueba: {name} ---", flush=True)
    
    img_p = "test_img.png"
    audio_p = "test_audio.mp3"
    out_p = f"output_{name.replace(' ', '_')}.mp4"
    
    cmd = ['ffmpeg', '-y'] + hw_args + [
        '-loop', '1', '-t', '10', '-i', img_p,
        '-i', audio_p,
        '-filter_complex', filter_complex,
        '-c:v', 'h264_nvenc', 
        '-preset', 'p1',
        '-pix_fmt', 'yuv420p',
        '-r', '24',
        '-c:a', 'aac',
        '-shortest',
        out_p
    ]
    
    start_time = time.time()
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    cpu_usages = []
    
    while process.poll() is None:
        cpu, _ = get_process_metrics(process.pid)
        if cpu > 0: cpu_usages.append(cpu)
        time.sleep(0.5)
    
    end_time = time.time()
    duration = end_time - start_time
    avg_cpu = statistics.mean(cpu_usages) if cpu_usages else 0
    
    print(f"Resultado {name}:", flush=True)
    print(f"  Tiempo total: {duration:.2f}s", flush=True)
    print(f"  CPU Promedio: {avg_cpu:.2f}%", flush=True)
    
    return duration, avg_cpu

if __name__ == "__main__":
    subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=1280x720', '-frames:v', '1', 'test_img.png'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-t', '10', 'test_audio.mp3'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Prueba 1: Híbrido (Lo que tienes ahora: HW Accel + Filtros CPU)
    hw_args_hybrid = ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda']
    filter_hybrid = "[0:v]scale=1280:720,boxblur=5:1,hwupload_cuda[bg]; [0:v]scale=-2:720,hwupload_cuda[fg]; [bg][fg]overlay_cuda=(W-w)/2:0"
    
    # Prueba 2: Puro GPU (Cero filtros CPU)
    hw_args_gpu = ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda']
    # Usamos scale_cuda para el "blur" (escalar a 32px y luego a 1280px crea un efecto borroso instantáneo en GPU)
    filter_gpu = (
        "[0:v]scale_cuda=32:18[small]; "
        "[small]scale_cuda=1280:720[bg]; "
        "[0:v]scale_cuda=-2:720[fg]; "
        "[bg][fg]overlay_cuda=x=(W-w)/2:y=0"
    )
    
    run_test("Hibrido (CPU Filters + NVENC)", filter_hybrid, hw_args_hybrid)
    run_test("Puro GPU (CUDA Filters + NVENC)", filter_gpu, hw_args_gpu)
    
    for f in ["test_img.png", "test_audio.mp3", "output_Hibrido_(CPU_Filters_+_NVENC).mp4", "output_Puro_GPU_(CUDA_Filters_+_NVENC).mp4"]:
        if os.path.exists(f): os.remove(f)
