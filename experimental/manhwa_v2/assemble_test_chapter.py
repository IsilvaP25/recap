import os
import subprocess
import fitz  # PyMuPDF
from PIL import Image

def assemble_manhwa_scroll(manga_name, chapter_num):
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pdf_path = os.path.join(base_dir, "pdf_storage", manga_name, f"Capitulo_{chapter_num}.pdf")
    audio_dir = os.path.join(base_dir, "outputs", manga_name, "_TEMP", f"Capitulo_{chapter_num}", "audio")
    temp_dir = os.path.join(base_dir, "experimental", "manhwa_v2", "temp_segments_v4")
    output_video = os.path.join(base_dir, "experimental", "manhwa_v2", f"test_{manga_name}_cap{chapter_num}.mp4")
    
    os.makedirs(temp_dir, exist_ok=True)
    
    # 1. Abrir PDF y procesar páginas
    doc = fitz.open(pdf_path)
    segments = []
    
    print(f"Procesando {len(doc)} páginas del Manhwa...")
    
    for i in range(len(doc)):
        page_num = i + 1
        audio_filename = f"PAGE_{page_num:02d}.mp3"
        audio_path = os.path.join(audio_dir, audio_filename)
        segment_path = os.path.join(temp_dir, f"seg_{page_num}.mp4")
        
        if os.path.exists(segment_path) and os.path.getsize(segment_path) > 1000:
            print(f"Segmento {page_num} ya existe, saltando...")
            segments.append(segment_path)
            continue

        if not os.path.exists(audio_path):
            print(f"Falta audio para página {page_num}, saltando...")
            continue
            
        # Extraer imagen con el zoom justo para el ancho objetivo (700px)
        page = doc.load_page(i)
        target_w = 700
        zoom = target_w / page.rect.width
        print(f"Extrayendo Página {page_num} (Zoom: {zoom:.2f})...")
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        img_path = os.path.join(temp_dir, f"p{page_num}.jpg") # Cambiado a JPG
        pix.save(img_path)
        
        # Ajuste de alto par para NVENC
        with Image.open(img_path) as img:
            w, h = img.size
            new_h = h if h % 2 == 0 else h - 1
            if new_h != h:
                img.crop((0, 0, w, new_h)).save(img_path, quality=95)
            new_h_final = new_h 

        # Medir duración audio
        cmd_dur = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
        duration = float(subprocess.check_output(cmd_dur).decode().strip())
        
        # Renderizar segmento con scroll SUAVE
        print(f"Renderizando Página {page_num} ({duration}s)...")
        
        # Si la imagen es más baja que 720, no hacemos scroll, la centramos
        if new_h_final <= 720:
            filter_complex = f"[0:v]pad=1280:720:(1280-{target_w})/2:(720-{new_h_final})/2:black[v]"
        else:
            filter_complex = (
                f"[0:v]pad=1280:ih:(1280-{target_w})/2:0:black,"
                f"crop=1280:720:0:(ih-720)*(t/{duration})[v]"
            )

        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-loop', '1', '-t', str(duration), '-i', img_path,
            '-i', audio_path,
            '-filter_complex', filter_complex,
            '-map', '[v]', '-map', '1:a',
            '-c:v', 'h264_nvenc', 
            '-preset', 'p4', 
            '-tune', 'hq',
            '-r', '24', 
            '-pix_fmt', 'yuv420p',
            '-shortest',
            segment_path
        ]
        subprocess.run(ffmpeg_cmd, check=True)
        segments.append(segment_path)

    # 3. Concatenar segmentos
    list_path = os.path.join(temp_dir, "list.txt")
    with open(list_path, 'w') as f:
        for s in segments:
            f.write(f"file '{os.path.abspath(s)}'\n")
            
    print("Concatenando capítulos...")
    concat_cmd = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
        '-i', list_path,
        '-c', 'copy',
        output_video
    ]
    subprocess.run(concat_cmd, check=True)
    print(f"\n¡PRUEBA FINALIZADA! Video generado en: {output_video}")

if __name__ == "__main__":
    assemble_manhwa_scroll("The_Max-Level_Player_s_100th_Regression", 2)
