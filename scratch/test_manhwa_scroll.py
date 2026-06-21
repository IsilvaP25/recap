import os
import subprocess
from PIL import Image

def test_scroll_video():
    images_dir = r"raw_downloads\The_Max-Level_Player_s_100th_Regression\Capitulo_1"
    output_video = "test_manhwa_scroll.mp4"
    img_name = "002.webp"
    dur = 10
    
    img_path = os.path.join(images_dir, img_name)
    img = Image.open(img_path)
    w, h = img.size
    
    # Scale width to 720
    target_w = 720
    target_h = int(h * (target_w / w))
    
    # Final video size 1280x720 (landscape) or 720x1280 (portrait)
    # Let's do 1280x720 for now to match their current mode
    v_w, v_h = 1280, 720
    
    # Filter for scrolling:
    # 1. Scale image to fit width (or a portion of width)
    # 2. Use overlay with animated y
    
    # We'll scale the image to height 2000 or something, but let's try scaling width to 400
    # so it's readable on a 720p screen.
    disp_w = 400
    disp_h = int(h * (disp_w / w))
    
    # PNG for ffmpeg
    os.makedirs("temp_test", exist_ok=True)
    png_path = os.path.join("temp_test", "scroll_img.png")
    img.save(png_path)
    
    # FFmpeg filter:
    # background is blurred version or black
    # fg is scaled image
    # y = - (disp_h - v_h) * (t / dur)
    
    filter_complex = (
        f"[0:v]scale={v_w}:{v_h}:force_original_aspect_ratio=increase,crop={v_w}:{v_h},boxblur=20:10[bg]; "
        f"[0:v]scale={disp_w}:-2[fg]; "
        f"[bg][fg]overlay=(main_w-overlay_w)/2:'if(lte(overlay_h,main_h), (main_h-overlay_h)/2, - (overlay_h-main_h)*(t/{dur}))'"
    )
    
    cmd = [
        'ffmpeg', '-y', '-loop', '1', '-t', str(dur), '-i', png_path,
        '-filter_complex', filter_complex,
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', '24', '-an',
        output_video
    ]
    
    print(f"Rendering scroll video for {img_name}...")
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"Scroll test video created: {output_video}")

if __name__ == "__main__":
    test_scroll_video()
