import os
import subprocess
import json

def generate_manhwa_video(image_path, audio_path, output_path):
    """
    Motor experimental de scroll vertical v2.0 (Aislado)
    - Usa h264_nvenc para GPU
    - Resolución 720p (1280x720)
    - Scroll fluido a 24fps
    """
    
    # 1. Obtener duración del audio (usando ffprobe)
    cmd_probe = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', audio_path
    ]
    try:
        duration = float(subprocess.check_output(cmd_probe).decode().strip())
    except Exception as e:
        print(f"Error midiendo audio: {e}")
        return

    # 2. Comando FFMPEG con Filtros Nvidia
    # - scale_npp: Escala por GPU (opcional, requiere ffmpeg compilado con NPP)
    # - crop: Realiza el desplazamiento vertical t*velocidad
    
    # Cálculo de velocidad: (Altura_Imagen - Altura_Video) / Duración
    # Altura_Video = 720
    # Usaremos una aproximación: la imagen se escala a 1280 de ancho.
    
    print(f"--- RENDERIZANDO MANHWA (EXPERIMENTAL) ---")
    print(f"Duración: {duration}s")
    
    ffmpeg_cmd = [
        'ffmpeg', '-y',
        '-hwaccel', 'cuda',
        '-i', image_path,
        '-i', audio_path,
        '-filter_complex', (
            f"[0:v]scale=1280:-1[scaled]; "  # Escalar a 720p ancho
            f"[scaled]crop=1280:720:0:'(ih-oh)*(t/{duration})'[v]" # Scroll proporcional al tiempo
        ),
        '-map', '[v]',
        '-map', '1:a',
        '-c:v', 'h264_nvenc',
        '-preset', 'p4',
        '-tune', 'hq',
        '-r', '24',
        '-pix_fmt', 'yuv420p',
        '-shortest',
        output_path
    ]
    
    try:
        subprocess.run(ffmpeg_cmd, check=True)
        print(f"¡Video generado con éxito!: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Fallo en FFMPEG: {e}")

if __name__ == "__main__":
    # Script de prueba rápida
    print("Modo experimental activo. Listo para procesar scroll vertical.")
