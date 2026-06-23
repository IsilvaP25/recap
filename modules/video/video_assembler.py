import os
import subprocess
import fitz
from PIL import Image, ImageDraw, ImageFont
import io
import argparse
import re
import sys
import multiprocessing
from multiprocessing import Pool
import random

# Función para subir la prioridad del proceso en Windows
def set_high_priority():
    try:
        if sys.platform == "win32":
            import psutil
            p = psutil.Process(os.getpid())
            p.nice(psutil.NORMAL_PRIORITY_CLASS)
            print("  [SISTEMA] Prioridad de renderizado establecida en 'Normal' (Máxima velocidad).")
    except Exception:
        pass

# Detectar núcleos y calcular hilos
CORES = multiprocessing.cpu_count()
THREADS = max(1, int(CORES * 0.9))
MAX_GPU_PARALLEL = 3 # Límite de sesiones NVENC simultáneas para evitar errores de driver

_encoder_cache = None

def get_encoder():
    global _encoder_cache
    if _encoder_cache is not None:
        return _encoder_cache
    try:
        res = subprocess.run(['ffmpeg', '-encoders'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        if "h264_nvenc" in res.stdout:
            _encoder_cache = "h264_nvenc"
        else:
            _encoder_cache = "libx264"
    except Exception:
        _encoder_cache = "libx264"
    return _encoder_cache

ENCODER = get_encoder()

def get_audio_duration(audio_path):
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try: return float(res.stdout)
    except: return 0.0

def get_active_word_index(words_data, current_time):
    if not words_data:
        return -1
    for idx, w in enumerate(words_data):
        if w["start"] <= current_time < w["end"]:
            return idx
    # Fallback al más cercano
    best_idx = 0
    min_diff = float('inf')
    for idx, w in enumerate(words_data):
        if w["end"] <= current_time:
            diff = current_time - w["end"]
            if diff < min_diff:
                min_diff = diff
                best_idx = idx
        elif w["start"] > current_time:
            diff = w["start"] - current_time
            if diff < min_diff:
                min_diff = diff
                best_idx = idx
    return best_idx

def calculate_scroll_params(img_w, img_h, canvas_w, canvas_h, duration):
    """
    Lógica Universal:
    - Si la imagen cabe: Estático centrado.
    - Si no cabe: Scroll con 0.5s de pausa al inicio y final.
    """
    if img_h <= canvas_h:
        return "(H-h)/2", False # Modo Estático

    # Ajuste de tiempo para el scroll
    margin = 0.5 if duration > 1.5 else 0.1
    scroll_duration = duration - (margin * 2)
    
    # Cálculo del scroll máximo (negativo para que la imagen suba)
    max_val = canvas_h - img_h
    y_logic = (
        f"if(lt(t,{margin}), 0, "
        f"if(lt(t,{duration-margin}), ({max_val})*((t-{margin})/{scroll_duration}), "
        f"{max_val}))"
    )
    
    return y_logic, True

def render_segment_task(args):
    """Tarea individual para renderizar una página en paralelo."""
    p_idx, dur, a_p, i, temp_dir, is_short, img_raw, current_ss, words_json_path, font_path = args
    p_num = p_idx + 1
    
    # Pre-escalado y Fondo
    img_opt = os.path.join(temp_dir, f"opt_{i:02d}.jpg")
    bg_opt = os.path.join(temp_dir, f"bg_{i:02d}.jpg")
    seg_p = os.path.join(temp_dir, f"s_{i:02d}.mp4")
    
    target_w = 720 if is_short else 700
    canvas_w, canvas_h = (720, 1280) if is_short else (1280, 720)
    
    # 1. Optimizar Imagen con PIL
    try:
        with Image.open(img_raw) as img:
            if img.mode in ("RGBA", "P"): img = img.convert("RGB")
            w, h = img.size
            # Calcular nuevas dimensiones manteniendo aspect ratio
            new_h = int(h * (target_w / w))
            # Asegurar dimensiones pares para NVENC
            if new_h % 2 != 0: new_h -= 1
            
            img_res = img.resize((target_w, new_h), Image.Resampling.LANCZOS)
            img_res.save(img_opt, quality=95)
            img_w, img_h = target_w, new_h
    except Exception as e:
        print(f"  [ERROR] PIL en página {i}: {e}")
        return None

    # Generar fondo negro sólido (Mucho más estable que blur por ahora)
    try:
        bg = Image.new('RGB', (canvas_w, canvas_h), color='black')
        bg.save(bg_opt, "JPEG")
    except Exception as e:
        print(f"  [ERROR] No se pudo crear el fondo: {e}")
        return None

    # 2. Calcular Scroll Dinámico
    y_filter, mode_manhwa = calculate_scroll_params(img_w, img_h, canvas_w, canvas_h, dur)
    
    # 3. Audio Silencioso si falta (solo para no-shorts)
    if not is_short and not a_p:
        silent_p = os.path.join(temp_dir, f"silent_{i:02d}.mp3")
        subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-t', str(dur), silent_p], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        a_p = silent_p

    # 4. Renderizado GPU (Optimizado)
    # Para shorts, usamos dur exacto. Para no-shorts, dur + 0.1 para evitar truncar audio por xfade
    render_dur = dur if is_short else dur + 0.1
    
    # Force Python frame-by-frame renderer for all modes to support drawing subtitles
    if True:
        # Cargar words_data desde JSON si existe
        import json
        words_data = []
        
        # If not short, locate page-specific words JSON
        if not is_short and a_p:
            words_json_path = os.path.join(os.path.dirname(a_p), f"PAGE_{p_num:02d}_words.json")
            
        if os.path.exists(words_json_path):
            try:
                with open(words_json_path, "r", encoding="utf-8") as f_json:
                    words_data = json.load(f_json)
            except Exception as e:
                print(f"  [WARNING] Error cargando JSON de palabras: {e}")
        
        # Cargar fuente
        font_size = 48
        try:
            font = ImageFont.truetype(font_path, font_size)
        except Exception as e:
            print(f"  [WARNING] No se pudo cargar la fuente {font_path}, usando default: {e}")
            font = ImageFont.load_default()

        # Iniciar proceso FFmpeg usando stdin para recibir frames rgb24
        fps = 24
        total_frames = int(render_dur * fps)
        
        # Preparar entrada de audio
        audio_args = []
        if a_p and os.path.exists(a_p):
            audio_args = ['-i', a_p, '-c:a', 'aac']
        else:
            # Fallback a silencio
            silent_p = os.path.join(temp_dir, f"silent_{i:02d}.mp3")
            if not os.path.exists(silent_p):
                subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-t', str(render_dur), silent_p], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            audio_args = ['-i', silent_p, '-c:a', 'aac']
            
        cmd = [
            'ffmpeg', '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-pix_fmt', 'rgb24',
            '-s', f'{canvas_w}x{canvas_h}',
            '-r', str(fps),
            '-i', '-',
        ] + audio_args + [
            '-map', '0:v',
            '-map', '1:a',
            '-t', f'{render_dur:.3f}',
            '-c:v', ENCODER, '-preset', 'p1', '-pix_fmt', 'yuv420p',
            seg_p
        ]
        
        try:
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"  [ERROR] No se pudo iniciar FFmpeg para segment_task {i}: {e}")
            return None
            
        # Parámetros para el scroll y texto
        word_spacing = 16
        y_center = 850 if is_short else 580
        
        # Cargar la imagen optimizada del manga
        try:
            manga_img = Image.open(img_opt)
        except Exception as e:
            print(f"  [ERROR] No se pudo abrir img_opt {img_opt}: {e}")
            return None
            
        margin = 0.5 if dur > 1.5 else 0.1
        scroll_duration = dur - (margin * 2)
        max_val = canvas_h - img_h
        
        for f_idx in range(total_frames):
            t = f_idx / fps
            
            # 1. Calcular offset y de scroll
            if img_h <= canvas_h:
                y_offset = (canvas_h - img_h) // 2
            else:
                if scroll_duration > 0:
                    if t < margin:
                        y_offset = 0
                    elif t < dur - margin:
                        y_offset = int(max_val * ((t - margin) / scroll_duration))
                    else:
                        y_offset = max_val
                else:
                    y_offset = 0
            
            # 2. Crear frame de canvas negro y pegar el manga
            frame = Image.new('RGB', (canvas_w, canvas_h), color='black')
            frame.paste(manga_img, ((canvas_w - img_w) // 2, y_offset))
            
            # 3. Dibujar subtítulos
            draw = ImageDraw.Draw(frame)
            time_offset = t + current_ss if is_short else t
            active_idx = get_active_word_index(words_data, time_offset)
            
            if active_idx != -1:
                # Construir ventana de 5 palabras
                window = []
                for offset in range(-2, 3):
                    idx = active_idx + offset
                    if 0 <= idx < len(words_data):
                        window.append((words_data[idx]["word"], offset == 0))
                    else:
                        window.append(("", False))
                
                # Dibujar con la Opción A
                active_word, _ = window[2]
                try:
                    active_w = draw.textlength(active_word, font=font)
                except:
                    active_w = len(active_word) * (font_size * 0.6)
                    
                x_center = canvas_w // 2
                x_coords = [0] * 5
                x_coords[2] = x_center - active_w / 2
                
                # Hacia la izquierda (W1, W0)
                w1_text, _ = window[1]
                if w1_text:
                    try: w1 = draw.textlength(w1_text, font=font)
                    except: w1 = len(w1_text) * (font_size * 0.6)
                    x_coords[1] = x_coords[2] - word_spacing - w1
                else:
                    x_coords[1] = x_coords[2]
                    
                w0_text, _ = window[0]
                if w0_text:
                    try: w0 = draw.textlength(w0_text, font=font)
                    except: w0 = len(w0_text) * (font_size * 0.6)
                    x_coords[0] = x_coords[1] - word_spacing - w0
                else:
                    x_coords[0] = x_coords[1]
                    
                # Hacia la derecha (W3, W4)
                w3_text, _ = window[3]
                x_coords[3] = x_coords[2] + active_w + word_spacing
                
                w4_text, _ = window[4]
                if w3_text:
                    try: w3 = draw.textlength(w3_text, font=font)
                    except: w3 = len(w3_text) * (font_size * 0.6)
                    x_coords[4] = x_coords[3] + w3 + word_spacing
                else:
                    x_coords[4] = x_coords[3]
                    
                # Renderizar en el frame
                for idx_word, (word, is_active) in enumerate(window):
                    if not word:
                        continue
                    fill = (255, 220, 0) if is_active else (255, 255, 255)
                    y_draw = y_center - font_size / 2
                    draw.text((x_coords[idx_word], y_draw), word, font=font, fill=fill, stroke_width=3, stroke_fill=(0, 0, 0))
            
            try:
                process.stdin.write(frame.tobytes())
            except Exception as e:
                print(f"  [ERROR] Error escribiendo frame al proceso FFmpeg: {e}")
                break
                
        try:
            process.stdin.close()
            process.wait()
        except:
            pass
            
        try:
            manga_img.close()
        except:
            pass
        
    # Limpieza inmediata
    for f in [img_raw, img_opt, bg_opt]:
        try: os.remove(f)
        except: pass
        
    return (seg_p, dur)


def assemble_video(manga_name, chapter_num, pdf_path, mode="full", page_limit=None, suffix=""):
    base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    work_dir = os.path.join(base_proj, "outputs", manga_name, "_TEMP", f"Capitulo_{chapter_num}")
    audio_dir = os.path.join(work_dir, "audio")
    video_dir = os.path.join(work_dir, "video")
    temp_dir = os.path.join(video_dir, "temp_segments")
    final_out_dir = os.path.join(base_proj, "outputs", manga_name, "VIDEOS")
    
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(final_out_dir, exist_ok=True)
    
    is_short = (mode == "short")
    prefix = "Short" if is_short else "Capitulo"
    video_filename = f"{prefix}_{chapter_num}_{suffix}.mp4" if suffix else f"{prefix}_{chapter_num}.mp4"
    out_video = os.path.join(final_out_dir, video_filename)
    
    if not os.path.exists(pdf_path): return

    doc = fitz.open(pdf_path)
    pts = []

    # Lógica de audio (Sincronización)
    audio_f = None
    audio_name = f"SHORT_FULL_{suffix}.mp3" if suffix else "SHORT_FULL.mp3"
    if is_short and os.path.exists(os.path.join(audio_dir, audio_name)):
        audio_f = os.path.join(audio_dir, audio_name)
        script_name = f"Short_guion_ESP_{suffix}.txt" if suffix else "Short_guion_ESP.txt"
        script_f = os.path.join(base_proj, "outputs", manga_name, "Scripts", script_name)
        if not os.path.exists(script_f): 
            raw_name = f"Short_guion_raw_{suffix}.txt" if suffix else "Short_guion_raw.txt"
            script_f = os.path.join(base_proj, "outputs", manga_name, "Scripts", raw_name)
            if not os.path.exists(script_f):
                specific_name = f"Short_guion_{suffix}.txt" if suffix else "Short_guion.txt"
                script_f = os.path.join(base_proj, "outputs", manga_name, "Scripts", specific_name)
        
        if os.path.exists(audio_f) and os.path.exists(script_f):
            total_dur = get_audio_duration(audio_f)
            with open(script_f, "r", encoding="utf-8") as f: s_text = f.read()
            matches_iter = list(re.finditer(r'\[(?:PAGE|PÁGINA|PAGINA)\s*[:\-\s]*(\d+)\]', s_text, flags=re.IGNORECASE))
            
            if not matches_iter:
                pages_found = [0, len(doc)//2, len(doc)-1]
                dur_per_page = total_dur / len(pages_found)
                current_ss = 0.0
                fps = 24
                for i, p_idx in enumerate(pages_found):
                    start_frame = int(current_ss * fps)
                    end_frame = int((current_ss + dur_per_page) * fps)
                    num_frames = end_frame - start_frame
                    actual_dur = num_frames / fps
                    actual_ss = start_frame / fps
                    
                    pts.append((p_idx, actual_dur, None, actual_ss))
                    current_ss += dur_per_page
            else:
                word_counts = []
                page_indices = []
                for m_idx, match in enumerate(matches_iter):
                    p_num_str = match.group(1)
                    p_idx = int(p_num_str) - 1
                    page_indices.append(p_idx)
                    
                    start_pos = match.end()
                    end_pos = matches_iter[m_idx + 1].start() if m_idx + 1 < len(matches_iter) else len(s_text)
                    page_text = s_text[start_pos:end_pos]
                    page_text_clean = re.sub(r'\[.*?\]', '', page_text).strip()
                    word_counts.append(len(page_text_clean.split()))
                
                total_words = sum(word_counts)
                current_ss = 0.0
                fps = 24
                for i, p_idx in enumerate(page_indices):
                    weight = word_counts[i] / total_words if total_words > 0 else 1/len(page_indices)
                    dur = total_dur * weight
                    
                    start_frame = int(current_ss * fps)
                    end_frame = int((current_ss + dur) * fps)
                    num_frames = end_frame - start_frame
                    actual_dur = num_frames / fps
                    actual_ss = start_frame / fps
                    
                    pts.append((p_idx, actual_dur, None, actual_ss))
                    current_ss += dur
    else:
        current_ss = 0.0
        for i in range(len(doc)):
            a_p = os.path.join(audio_dir, f"PAGE_{i+1:02d}.mp3")
            if os.path.exists(a_p):
                d = get_audio_duration(a_p)
                if d > 0:
                    pts.append((i, d, a_p, current_ss))
                    current_ss += d
            else:
                # Fallback para pruebas sin audio
                pts.append((i, 5.0, None, current_ss))
                current_ss += 5.0

    if not pts: doc.close(); return

    # Aplicar límite de páginas si se solicita (Ej: para pruebas rápidas del 25%)
    if page_limit:
        print(f"  [DEBUG] Aplicando límite de {page_limit} páginas para prueba rápida.")
        pts = pts[:page_limit]

    # --- EXTRACCIÓN DE IMÁGENES OPTIMIZADA ---
    target_w = 720 if is_short else 700
    print(f"[{mode.upper()}] Preparando {len(pts)} páginas a {target_w}px de ancho...")
    
    words_name = f"SHORT_FULL_{suffix}_words.json" if suffix else "SHORT_FULL_words.json"
    words_json_path = os.path.join(audio_dir, words_name)
    font_path = os.path.join(base_proj, "Lato-Black.ttf")
    
    task_args = []
    for i, (p_idx, dur, a_p, current_ss) in enumerate(pts):
        page = doc.load_page(p_idx if p_idx < len(doc) else 0)
        # Calcular zoom justo para el ancho objetivo
        zoom = target_w / page.rect.width
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        img_raw = os.path.join(temp_dir, f"raw_{i:02d}.jpg")
        pix.save(img_raw)
        task_args.append((p_idx, dur, a_p, i, temp_dir, is_short, img_raw, current_ss, words_json_path, font_path))
    
    doc.close()

    # --- RENDERIZADO EN PARALELO ---
    print(f"[{mode.upper()}] Renderizando en paralelo (GPU Sessions: {MAX_GPU_PARALLEL})...")
    
    total_tasks = len(task_args)
    completed = 0
    
    def print_progress(completed, total, prefix=''):
        import sys
        longitud = 10
        porcentaje = f"{100 * (completed / float(total)):.1f}%"
        llenado = int(longitud * completed // total)
        barra = '#' * llenado + '-' * (longitud - llenado)
        linea = f"\r\x1b[K{prefix[:20]} |{barra}| {porcentaje}"
        sys.stdout.write(linea)
        sys.stdout.flush()

    def cb(res):
        nonlocal completed
        completed += 1
        print_progress(completed, total_tasks, "Render Video")

    print_progress(0, total_tasks, "Render Video")
    with Pool(processes=MAX_GPU_PARALLEL) as pool:
        async_results = [pool.apply_async(render_segment_task, (arg,), callback=cb) for arg in task_args]
        segs = [r.get() for r in async_results]
    print()
    
    # --- ENSAMBLAJE FINAL ---
    if segs:
        master_audio = os.path.join(temp_dir, "master_audio.mp3")
        a_inputs = [p[2] for p in pts if p[2]]
        
        if a_inputs:
            with open(os.path.join(temp_dir, "audio_lst.txt"), "w") as f:
                for a in a_inputs:
                    safe_p = os.path.abspath(a).replace('\\', '/')
                    f.write(f"file '{safe_p}'\n")
            subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.join(temp_dir, "audio_lst.txt"), '-c', 'copy', master_audio], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # --- AÑADIR CTA AL FINAL (Solo Shorts) ---
        if is_short:
            print("  Añadiendo CTA Final (5s)...")
            cta_img_p = os.path.join(temp_dir, "cta_final.png")
            cta_vid_p = os.path.join(temp_dir, "cta_final.mp4")
            
            cta_img = Image.new('RGB', (720, 1280), color=(10, 10, 10))
            draw = ImageDraw.Draw(cta_img)
            try:
                # Usar Lato-Black.ttf para mantener la tipografía
                font = ImageFont.truetype(font_path, 50)
            except:
                try:
                    font = ImageFont.truetype("arial.ttf", 50)
                except:
                    font = ImageFont.load_default()
            
            text = "¿Quieres el\nresumen completo?\nComenta"
            # Centrado compatible
            w, h = 400, 200 # Fallback sizes
            try:
                bbox = draw.textbbox((0, 0), text, font=font, align="center")
                w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except: pass
            
            draw.multiline_text(((720-w)/2, (1280-h)/2), text, font=font, fill=(255, 255, 255), align="center", spacing=20)
            cta_img.save(cta_img_p)
            
            # Generar video de CTA silencioso (sin pista de audio)
            subprocess.run(['ffmpeg', '-y', '-loop', '1', '-i', cta_img_p, '-t', '5', '-c:v', ENCODER, '-preset', 'p1', '-pix_fmt', 'yuv420p', '-r', '24', cta_vid_p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(cta_vid_p):
                segs.append((cta_vid_p, 5.0))

        if is_short:
            # --- ENSAMBLAJE PARA SHORTS (Cortes directos sin recodificar + Mux de audio master) ---
            print(f"  [SHORT] Concatenando {len(segs)} segmentos con cortes directos...")
            concat_list_path = os.path.join(temp_dir, "concat_list.txt")
            with open(concat_list_path, "w", encoding="utf-8") as f:
                for s, _ in segs:
                    safe_s = os.path.abspath(s).replace('\\', '/')
                    f.write(f"file '{safe_s}'\n")
            
            temp_merged_video = os.path.join(temp_dir, "temp_merged_video.mp4")
            cmd_concat = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_list_path,
                '-c', 'copy',
                temp_merged_video
            ]
            rf_concat = subprocess.run(cmd_concat, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if rf_concat.returncode != 0:
                print(f"  [ERROR] Falló la concatenación de segmentos: {rf_concat.stderr}")
                return
            
            if audio_f and os.path.exists(audio_f):
                print(f"  [SHORT] Mezclando audio master '{audio_f}' con video...")
                cmd_mux = [
                    'ffmpeg', '-y',
                    '-i', temp_merged_video,
                    '-i', audio_f,
                    '-map', '0:v',
                    '-map', '1:a?',
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    out_video
                ]
                rf_mux = subprocess.run(cmd_mux, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if rf_mux.returncode == 0:
                    print(f"¡EXITO Short sincronizado!: {out_video}")
                else:
                    print(f"  [ERROR] Falló el mux final de audio: {rf_mux.stderr}")
            else:
                # Fallback sin audio
                print(f"  [AVISO] No se encontró audio master para el Short, copiando video silencioso.")
                cmd_copy = ['ffmpeg', '-y', '-i', temp_merged_video, '-c', 'copy', out_video]
                subprocess.run(cmd_copy, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # --- ENSAMBLAJE PARA RECAP COMPLETO (Sigue usando xfade y master_audio) ---
            print(f"  Uniendo clips con transiciones XFade...")
            effects = ['fade', 'wipeleft', 'wiperight', 'wipeup', 'wipedown', 'slideleft', 'slideright', 'slideup', 'slidedown', 'circleopen', 'dissolve', 'pixelize']
            
            f_cmd = ['ffmpeg', '-y']
            for s, _ in segs: f_cmd += ['-i', s]
            
            if os.path.exists(master_audio):
                f_cmd += ['-i', master_audio]
                audio_idx = len(segs)
                a_filter = None
            else: a_filter = None

            filter_parts = []
            last_out = "[0:v]"
            current_offset = segs[0][1]
            
            for i in range(1, len(segs)):
                effect = random.choice(effects)
                offset = max(0, current_offset - 0.5)
                out_label = f"[v{i}]"
                filter_parts.append(f"{last_out}[{i}:v]xfade=transition={effect}:duration=0.5:offset={offset}{out_label}")
                last_out = out_label
                current_offset = offset + segs[i][1]

            if len(segs) > 1:
                full_filter = "; ".join(filter_parts)
                f_cmd += ['-filter_complex', full_filter]
                f_cmd += ['-map', last_out]
                if os.path.exists(master_audio): f_cmd += ['-map', f'{audio_idx}:a']
            else:
                f_cmd += ['-map', '0:v']
                if os.path.exists(master_audio): f_cmd += ['-map', '0:a']
            
            f_cmd += ['-c:v', ENCODER, '-preset', 'p1', '-pix_fmt', 'yuv420p', '-r', '24', '-c:a', 'aac', out_video]
            
            rf = subprocess.run(f_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if rf.returncode == 0: 
                print(f"¡EXITO!: {out_video}")
            else: 
                print(f"  [AVISO] Falló el ensamblaje final.")
                print(f"  [DETALLE FFMPEG]: {rf.stderr[-500:]}") # Mostrar los últimos 500 caracteres del error

def assemble_master_recap(manga_name, chapters):
    print(f"\n--- ENSAMBLANDO MEGA RECAP (Capítulos {chapters[0]}-{chapters[-1]}) ---")
    base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    final_out_dir = os.path.join(base_proj, "outputs", manga_name, "VIDEOS")
    out_master = os.path.join(final_out_dir, f"MegaRecap_{chapters[0]}_al_{chapters[-1]}.mp4")
    
    all_segs = []
    for cap in chapters:
        cap_temp_dir = os.path.join(base_proj, "outputs", manga_name, "_TEMP", f"Capitulo_{cap}", "video", "temp_segments")
        if os.path.exists(cap_temp_dir):
            segs = sorted([os.path.join(cap_temp_dir, f) for f in os.listdir(cap_temp_dir) if f.endswith(".mp4")])
            all_segs.extend(segs)
            
    if not all_segs: return
        
    list_path = os.path.join("temp", "master_concat_list.txt")
    os.makedirs("temp", exist_ok=True)
    with open(list_path, "w", encoding="utf-8") as f:
        for s in all_segs:
            safe_s = os.path.abspath(s).replace('\\', '/')
            f.write(f"file '{safe_s}'\n")
            
    cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_path, '-c', 'copy', out_master]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  [OK] MEGA RECAP CREADO: {out_master}")
    return out_master

if __name__ == "__main__":
    set_high_priority()
    parser = argparse.ArgumentParser()
    parser.add_argument("--manga", required=True); parser.add_argument("--chapter"); parser.add_argument("--pdf", required=True); parser.add_argument("--mode", default="both")
    parser.add_argument("--master", action="store_true"); parser.add_argument("--chapters", nargs="+")
    parser.add_argument("--suffix", default="")
    args = parser.parse_args()
    
    if args.master and args.chapters: assemble_master_recap(args.manga, args.chapters)
    else:
        if args.mode in ["full", "both"]: assemble_video(args.manga, args.chapter, args.pdf, mode="full")
        if args.mode in ["short", "both"]: assemble_video(args.manga, args.chapter, args.pdf, mode="short", suffix=args.suffix)
