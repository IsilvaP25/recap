import os
import sys
import time
import subprocess

class QuotaExceededException(Exception):
    """Excepción lanzada cuando se supera la cuota diaria de YouTube (error 42)."""
    pass

class ApiKeyExhaustedException(Exception):
    """Excepción lanzada cuando se agotan todas las API keys de Gemini (error 43)."""
    pass

def run_pipeline_step(step_name, command):
    print(f"\n{'='*50}")
    print(f"INICIANDO PASO: {step_name}")
    print(f"{'='*50}")
    
    # Get the base directory of the current script
    # This assumes common.py is in modules/flows/
    base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    start_time = time.time()
    try:
        env = os.environ.copy()
        
        # Add project root and modules/pipeline to PYTHONPATH
        pipeline_path = os.path.join(base_proj, "modules", "pipeline")
        env["PYTHONPATH"] = base_proj + os.pathsep + pipeline_path + os.pathsep + env.get("PYTHONPATH", "")
        
        # Resolve the script path to an absolute path
        script_path = command[0]
        if not os.path.isabs(script_path):
            script_path = os.path.join(base_proj, script_path)
        
        # Execute with cwd set to project root, inheriting standard streams for interactive support
        process = subprocess.Popen(
            [sys.executable, script_path] + command[1:],
            env=env,
            cwd=base_proj
        )
        process.wait()
        
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command)
            
        end_time = time.time()
        print(f"\n[SUCCESS] {step_name} completado en {end_time - start_time:.2f} segundos.")
        return True
    except subprocess.CalledProcessError as e:
        if e.returncode == 42:
            print(f"\n[ERROR] El paso '{step_name}' falló debido a que se excedió la cuota diaria de YouTube.")
            raise QuotaExceededException("Se ha alcanzado la cuota diaria de subidas de videos en YouTube.")
        elif e.returncode == 43:
            print(f"\n[CRITICAL] El paso '{step_name}' falló porque se agotaron todas las API keys de Gemini.")
            raise ApiKeyExhaustedException("Se han agotado todas las API keys de Gemini.")
        print(f"\n[ERROR] El paso '{step_name}' falló con código de salida {e.returncode}.")
        return False


def has_pending_pdfs(manga_name, pdf_base, db_path):
    import re
    import sqlite3
    
    pdf_dir = os.path.join(pdf_base, manga_name)
    if not os.path.exists(pdf_dir):
        return False
        
    pending_count = 0
        
    def extract_num(fn):
        m = re.search(r'(\d+\.\d+|\d+)', fn)
        return float(m.group(1)) if m else 0.0
        
    pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith(".pdf")]
    if not pdf_files:
        return False
        
    manga_key = manga_name.replace(' ', '_')
    
    # Conectarse a la base de datos para obtener partes completadas
    completed_parts = []
    has_short_in_db = False
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT start_chapter, end_chapter FROM pipeline_parts 
                WHERE manga = ? AND status = 'completed'
            ''', (manga_key,))
            completed_parts = [(float(row[0]), float(row[1])) for row in cursor.fetchall()]
            
            # Comprobar si existe Short registrado en la DB
            cursor.execute('''
                SELECT count(*) FROM shorts 
                WHERE manga = ? AND (video_created = 1 OR is_uploaded >= 1)
            ''', (manga_key,))
            has_short_in_db = cursor.fetchone()[0] > 0
            conn.close()
        except Exception as e:
            print(f"Error al consultar la base de datos para {manga_name}: {e}")
            
    # Directorios de salida
    base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    manga_out_dir = os.path.join(base_proj, "outputs", manga_name)
    videos_dir = os.path.join(manga_out_dir, "VIDEOS")
    pub_dir = os.path.join(manga_out_dir, "FINAL_PUBLICATION")
    
    for f in pdf_files:
        cap_num = extract_num(f)
        
        # 0. Si es el capítulo 1, comprobar si ya se hizo video tipo Short (Gancho Inicial)
        if cap_num == 1.0:
            if has_short_in_db:
                continue
            if os.path.exists(os.path.join(videos_dir, "Short_1.mp4")):
                continue
            if os.path.exists(os.path.join(pub_dir, "Short_Gancho_Inicial", "short_video.mp4")):
                continue
        
        # 1. Comprobar si está cubierto por alguna parte completada en DB
        is_completed = False
        for start_c, end_c in completed_parts:
            if start_c <= cap_num <= end_c:
                is_completed = True
                break
        if is_completed:
            continue
            
        # 2. Comprobar si existe el video individual del capítulo
        def format_cap(num):
            return str(int(num)) if num == int(num) else str(num)
        cap_str = format_cap(cap_num)
        
        if os.path.exists(os.path.join(videos_dir, f"Capitulo_{cap_str}.mp4")):
            continue
            
        # 3. Comprobar si está en algún MegaRecap en disco
        if os.path.exists(videos_dir):
            for vf in os.listdir(videos_dir):
                if vf.startswith("MegaRecap_") and vf.endswith(".mp4"):
                    m = re.match(r'MegaRecap_([\d\.]+)_al_([\d\.]+)\.mp4', vf)
                    if m:
                        try:
                            start_c = float(m.group(1))
                            end_c = float(m.group(2))
                            if start_c <= cap_num <= end_c:
                                is_completed = True
                                break
                        except ValueError:
                            pass
            if is_completed:
                continue
                
        # 4. Comprobar si está cubierto por alguna carpeta consolidada lista para publicar
        if os.path.exists(pub_dir):
            for d in os.listdir(pub_dir):
                if d.startswith("Recap_Parte_") and os.path.isdir(os.path.join(pub_dir, d)):
                    m = re.search(r'_Caps_([\d\.]+)_al_([\d\.]+)$', d)
                    if m:
                        try:
                            start_c = float(m.group(1))
                            end_c = float(m.group(2))
                            if start_c <= cap_num <= end_c:
                                if os.path.exists(os.path.join(pub_dir, d, "video_final.mp4")):
                                    is_completed = True
                                    break
                        except ValueError:
                            pass
            if is_completed:
                continue
                
        # Si llegamos aquí, este PDF no está completado.
        pending_count += 1
        
    return pending_count >= 7


