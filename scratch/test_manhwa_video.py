import os
import subprocess
from PIL import Image
import io

def test_video_only():
    manga_name = "The_Max-Level_Player_s_100th_Regression"
    images_dir = r"raw_downloads\The_Max-Level_Player_s_100th_Regression\Capitulo_1"
    output_video = "test_manhwa_video.mp4"
    
    selected_images = ["001.webp", "002.webp", "003.webp"]
    dur_per_image = 5
    
    # Create temp dir for segments
    os.makedirs("temp_test", exist_ok=True)
    segments = []
    
    for i, img_name in enumerate(selected_images):
        img_path = os.path.join(images_dir, img_name)
        img = Image.open(img_path)
        # Convert to PNG for ffmpeg
        png_path = os.path.join("temp_test", f"img_{i}.png")
        img.save(png_path)
        
        seg_path = os.path.join("temp_test", f"seg_{i}.mp4")
        
        # CURRENT LOGIC from video_assembler.py (landscape)
        # [0:v]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,boxblur=20:10[bg]; 
        # [0:v]scale=-2:720[fg]; 
        # [bg][fg]overlay=(main_w-overlay_w)/2:0
        
        filter_complex = (
            f"[0:v]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,boxblur=20:10[bg]; "
            f"[0:v]scale=-2:720[fg]; "
            f"[bg][fg]overlay=(main_w-overlay_w)/2:0"
        )
        
        cmd = [
            'ffmpeg', '-y', '-loop', '1', '-t', str(dur_per_image), '-i', png_path,
            '-filter_complex', filter_complex,
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', '24', '-an',
            seg_path
        ]
        
        print(f"Rendering segment {i} ({img_name})...")
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        segments.append(seg_path)
    
    # Concat segments
    with open("temp_test/list.txt", "w") as f:
        for s in segments:
            abs_p = os.path.abspath(s).replace('\\', '/')
            f.write(f"file '{abs_p}'\n")
            
    concat_cmd = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', "temp_test/list.txt",
        '-c', 'copy', output_video
    ]
    print("Concatenating segments...")
    subprocess.run(concat_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"Test video created: {output_video}")

if __name__ == "__main__":
    test_video_only()
