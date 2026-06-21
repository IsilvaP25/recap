import os
import subprocess

def test_single_clip():
    base_proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manga_name = "The_Max-Level_Player_s_100th_Regression"
    temp_dir = os.path.join(base_proj, "outputs", manga_name, "_TEMP", "Capitulo_3", "video", "temp_segments")
    audio_path = os.path.join(base_proj, "outputs", manga_name, "_TEMP", "Capitulo_3", "audio", "PAGE_01.mp3")
    img_opt = os.path.join(temp_dir, "opt_00.jpg")
    bg_opt = os.path.join(temp_dir, "bg_00.jpg")
    seg_p = os.path.join(temp_dir, "test_clip.mp4")

    # Asegurarse de que existan (al menos opt y bg de la ultima prueba fallida deberian estar... oh wait, el script los borra)
    # Mejor probamos con imagenes de prueba que creamos al vuelo
    from PIL import Image
    os.makedirs(temp_dir, exist_ok=True)
    Image.new('RGB', (1280, 720), color='black').save(bg_opt)
    Image.new('RGB', (700, 3000), color='red').save(img_opt)
    
    # Crear un audio dummy si no existe
    if not os.path.exists(audio_path):
        subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-t', '5', audio_path], stderr=subprocess.DEVNULL)

    y_filter = "if(lt(t\\,0.5)\\, 0\\, if(lt(t\\,4.5)\\, (-2280)*((t-0.5)/4.0)\\, -2280))"
    f_c = f"[0:v][1:v]overlay=x=(W-w)/2:y={y_filter}:format=yuv420"
    
    cmd = [
        'ffmpeg', '-y', 
        '-loop', '1', '-t', '5.1', '-i', bg_opt,
        '-loop', '1', '-t', '5.1', '-i', img_opt,
        '-i', audio_path,
        '-filter_complex', f_c,
        '-c:v', 'h264_nvenc', '-preset', 'p1', '-pix_fmt', 'yuv420p', '-r', '24',
        '-c:a', 'aac', '-shortest',
        seg_p
    ]
    
    print("Ejecutando comando FFMPEG...")
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    print("\n--- SALIDA COMPLETA FFMPEG ---")
    print(res.stderr)
    
    if res.returncode == 0:
        print("¡Exito! El clip se genero correctamente.")
    else:
        print("Fallo el clip.")

if __name__ == "__main__":
    test_single_clip()
