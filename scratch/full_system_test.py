import os
import subprocess
import time
import psutil
import sys
from PIL import Image

# CONFIGURACIÓN DEL TEST
MANGA = "The_Max-Level_Player_s_100th_Regression"
CHAPTER = 1
PAGE_NUM = 1
BASE_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_PATH = os.path.join(BASE_PROJ, "pdf_storage", MANGA, f"Capitulo_{CHAPTER}.pdf")

# Rutas de módulos
SCRIPTWRITER = os.path.join(BASE_PROJ, "modules", "pipeline", "manga_scriptwriter.py")
AUDIO_GEN = os.path.join(BASE_PROJ, "modules", "pipeline", "audio_generator.py")
VIDEO_GEN = os.path.join(BASE_PROJ, "modules", "pipeline", "video_assembler.py")

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

def monitor_resources(stop_event, stats):
    while not stop_event['stop']:
        c, r, g = get_metrics()
        stats['cpu'].append(c)
        stats['ram'].append(r)
        stats['gpu'].append(g)
        time.sleep(0.5)

def run_step(name, command, env=None):
    print(f"\n>>> INICIANDO: {name}...")
    start = time.time()
    
    # Monitoreo
    stop_event = {'stop': False}
    stats = {'cpu': [], 'ram': [], 'gpu': []}
    
    import threading
    t = threading.Thread(target=monitor_resources, args=(stop_event, stats))
    t.start()
    
    try:
        # Ejecutar comando
        result = subprocess.run([sys.executable] + command, env=env, cwd=BASE_PROJ, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error en {name}: {result.stderr}")
    finally:
        stop_event['stop'] = True
        t.join()
        
    end = time.time()
    dur = end - start
    
    avg_cpu = sum(stats['cpu']) / len(stats['cpu']) if stats['cpu'] else 0
    avg_ram = sum(stats['ram']) / len(stats['ram']) if stats['ram'] else 0
    avg_gpu = sum(stats['gpu']) / len(stats['gpu']) if stats['gpu'] else 0
    
    print(f"--- {name} COMPLETADO ---")
    print(f"Tiempo: {dur:.2f}s")
    print(f"CPU: {avg_cpu:.1f}% | RAM: {avg_ram:.1f}% | GPU: {avg_gpu:.1f}%")
    
    return {
        'name': name,
        'duration': dur,
        'cpu': avg_cpu,
        'ram': avg_ram,
        'gpu': avg_gpu
    }

def main():
    print("="*60)
    print(f"TEST DE SISTEMA COMPLETO (1 PÁGINA: {MANGA} Cap {CHAPTER})")
    print("="*60)
    
    if not os.path.exists(PDF_PATH):
        print(f"Error: No se encuentra el PDF en {PDF_PATH}")
        return

    results = []
    
    # Configurar environment
    env = os.environ.copy()
    env["PYTHONPATH"] = BASE_PROJ + os.pathsep + os.path.join(BASE_PROJ, "modules") + os.pathsep + env.get("PYTHONPATH", "")

    # PASO 1: GENERACIÓN DE GUIÓN (IA VISION)
    # Limitamos a 1 página para el test
    results.append(run_step("FASE 1: GUIÓN (IA Vision)", 
                            [SCRIPTWRITER, "--manga", MANGA, "--chapter", str(CHAPTER), "--pdf", PDF_PATH, "--mode", "full", "--batch_size", "1"],
                            env=env))

    # PASO 2: GENERACIÓN DE AUDIO (TTS)
    results.append(run_step("FASE 2: AUDIO (TTS)", 
                            [AUDIO_GEN, "--manga", MANGA, "--chapter", str(CHAPTER), "--mode", "full"],
                            env=env))

    # PASO 3: RENDERIZADO DE VIDEO (GPU)
    # Usamos el assembler normal pero solo para el segmento de la pág 1
    results.append(run_step("FASE 3: VIDEO (GPU Render)", 
                            [VIDEO_GEN, "--manga", MANGA, "--chapter", str(CHAPTER), "--pdf", PDF_PATH, "--mode", "full"],
                            env=env))

    # RESUMEN FINAL
    print("\n" + "="*60)
    print("RESUMEN DE RECURSOS Y TIEMPOS")
    print("="*60)
    total_time = sum(r['duration'] for r in results)
    
    for r in results:
        print(f"{r['name']:<25} | {r['duration']:>6.2f}s | CPU: {r['cpu']:>4.1f}% | GPU: {r['gpu']:>4.1f}%")
    
    print("-"*60)
    print(f"{'TIEMPO TOTAL':<25} | {total_time:>6.2f}s")
    print("="*60)

if __name__ == "__main__":
    main()
