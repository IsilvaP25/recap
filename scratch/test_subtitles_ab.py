import asyncio
import os
import sys
import edge_tts
from PIL import Image, ImageDraw, ImageFont
import subprocess

VOICE = "es-ES-AlvaroNeural"
RATE = "+25%"
TEXT = "había una vez un cazador que vivía en el bosque y buscaba su presa"
FONT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Lato-Black.ttf")
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

async def generate_audio_and_boundaries():
    print("Generando audio y word boundaries con edge-tts...")
    communicate = edge_tts.Communicate(TEXT, VOICE, rate=RATE, boundary="WordBoundary")
    audio_path = os.path.join(OUTPUT_DIR, "test_audio.mp3")
    
    words_data = []
    with open(audio_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # Convert ticks to seconds
                offset_sec = chunk["offset"] / 10000000.0
                duration_sec = chunk["duration"] / 10000000.0
                text = chunk["text"]
                words_data.append({
                    "word": text,
                    "start": offset_sec,
                    "end": offset_sec + duration_sec
                })
    
    print(f"Audio guardado en {audio_path}")
    print(f"Se capturaron {len(words_data)} palabras.")
    return audio_path, words_data

def get_audio_duration(audio_path):
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try: return float(res.stdout)
    except: return 0.0

def get_active_word_index(words_data, current_time):
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

def render_video(mode, audio_path, words_data, output_video_path):
    duration = get_audio_duration(audio_path)
    if duration <= 0:
        duration = 5.0  # fallback
    
    # Limitar a unos 5 segundos
    duration = min(duration, 5.0)
    print(f"Renderizando {mode} ({duration:.2f}s) a 24 FPS...")
    
    fps = 24
    total_frames = int(duration * fps)
    
    canvas_w, canvas_h = 720, 1280
    font_size = 48
    word_spacing = 16
    y_center = 850
    
    # Cargar fuente
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except Exception as e:
        print(f"No se pudo cargar la fuente en {FONT_PATH}, usando default: {e}")
        font = ImageFont.load_default()

    # Iniciar proceso FFmpeg
    # Usamos libx264 o h264_nvenc para máxima compatibilidad
    cmd = [
        'ffmpeg', '-y',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-pix_fmt', 'rgb24',
        '-s', f'{canvas_w}x{canvas_h}',
        '-r', str(fps),
        '-i', '-',
        '-i', audio_path,
        '-t', f'{duration:.3f}',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'ultrafast',
        '-c:a', 'aac', '-shortest',
        output_video_path
    ]
    
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    for f_idx in range(total_frames):
        t = f_idx / fps
        
        # Crear frame de fondo gris oscuro
        frame = Image.new('RGB', (canvas_w, canvas_h), color=(30, 30, 30))
        draw = ImageDraw.Draw(frame)
        
        # Obtener palabra activa
        active_idx = get_active_word_index(words_data, t)
        
        # Construir ventana de 5 palabras
        window = []
        for offset in range(-2, 3):
            idx = active_idx + offset
            if 0 <= idx < len(words_data):
                window.append((words_data[idx]["word"], offset == 0)) # (palabra, es_activa)
            else:
                window.append(("", False))
        
        if mode == "A":
            # Opción A: Palabra activa centrada exactamente en X=360
            active_word, _ = window[2]
            
            # Calcular ancho de la palabra activa
            try:
                active_w = draw.textlength(active_word, font=font)
            except:
                active_w = len(active_word) * (font_size * 0.6)
                
            x_coords = [0] * 5
            x_coords[2] = 360 - active_w / 2
            
            # Calcular hacia la izquierda
            # W1
            w1_text, _ = window[1]
            if w1_text:
                try: w1 = draw.textlength(w1_text, font=font)
                except: w1 = len(w1_text) * (font_size * 0.6)
                x_coords[1] = x_coords[2] - word_spacing - w1
            else:
                x_coords[1] = x_coords[2]
                
            # W0
            w0_text, _ = window[0]
            if w0_text:
                try: w0 = draw.textlength(w0_text, font=font)
                except: w0 = len(w0_text) * (font_size * 0.6)
                x_coords[0] = x_coords[1] - word_spacing - w0
            else:
                x_coords[0] = x_coords[1]
                
            # W3
            w3_text, _ = window[3]
            x_coords[3] = x_coords[2] + active_w + word_spacing
            
            # W4
            w4_text, _ = window[4]
            if w3_text:
                try: w3 = draw.textlength(w3_text, font=font)
                except: w3 = len(w3_text) * (font_size * 0.6)
                x_coords[4] = x_coords[3] + w3 + word_spacing
            else:
                x_coords[4] = x_coords[3]
                
            # Dibujar
            for i, (word, is_active) in enumerate(window):
                if not word:
                    continue
                fill = (255, 220, 0) if is_active else (255, 255, 255)
                # Centrar verticalmente aproximado
                y_draw = y_center - font_size / 2
                draw.text((x_coords[i], y_draw), word, font=font, fill=fill, stroke_width=3, stroke_fill=(0, 0, 0))
                
        elif mode == "B":
            # Opción B: Bloque completo de palabras centradas
            # Filtrar palabras no vacías en la ventana y calcular anchos
            active_words_in_window = []
            for i, (word, is_active) in enumerate(window):
                if word:
                    try: w = draw.textlength(word, font=font)
                    except: w = len(word) * (font_size * 0.6)
                    active_words_in_window.append({
                        "word": word,
                        "width": w,
                        "is_active": is_active
                    })
            
            if active_words_in_window:
                total_w = sum(item["width"] for item in active_words_in_window) + (len(active_words_in_window) - 1) * word_spacing
                x_start = 360 - total_w / 2
                
                curr_x = x_start
                for item in active_words_in_window:
                    fill = (255, 220, 0) if item["is_active"] else (255, 255, 255)
                    y_draw = y_center - font_size / 2
                    draw.text((curr_x, y_draw), item["word"], font=font, fill=fill, stroke_width=3, stroke_fill=(0, 0, 0))
                    curr_x += item["width"] + word_spacing
        
        # Escribir frame al proceso FFmpeg
        process.stdin.write(frame.tobytes())
        
    process.stdin.close()
    process.wait()
    print(f"¡Renderizado completado!: {output_video_path}")

async def main():
    audio_path, words_data = await generate_audio_and_boundaries()
    
    out_a = os.path.join(OUTPUT_DIR, "test_option_a.mp4")
    out_b = os.path.join(OUTPUT_DIR, "test_option_b.mp4")
    
    render_video("A", audio_path, words_data, out_a)
    render_video("B", audio_path, words_data, out_b)
    
    # Copiar a la carpeta de artefactos de gemini para que el usuario pueda verlos
    artifacts_dir = r"C:\Users\ignacio\.gemini\antigravity\brain\360b17bf-9ce2-460e-b188-8f0803a2b7ac"
    if os.path.exists(artifacts_dir):
        import shutil
        shutil.copy(out_a, os.path.join(artifacts_dir, "test_option_a.mp4"))
        shutil.copy(out_b, os.path.join(artifacts_dir, "test_option_b.mp4"))
        print("Videos copiados a la carpeta de artefactos de Gemini.")

if __name__ == "__main__":
    asyncio.run(main())
