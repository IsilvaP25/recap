import os
import subprocess
import json

def main():
    video_path = r"outputs\Single_Dad_In_Another_World\VIDEOS\Short_1.mp4"
    if not os.path.exists(video_path):
        print(f"File not found: {video_path}")
        return
        
    print("Checking audio levels in different segments of the output video...")
    # Analyze the volume of the audio using ffmpeg volumedetect filter in 5-second intervals,
    # or let's use astats filter to see if it's dead silent.
    # Let's extract the audio to wav and read it.
    wav_path = "temp_test_audio.wav"
    subprocess.run([
        'ffmpeg', '-y', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', wav_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if not os.path.exists(wav_path):
        print("Failed to extract audio.")
        return
        
    import wave
    import struct
    
    with wave.open(wav_path, "rb") as w:
        params = w.getparams()
        nchannels, sampwidth, framerate, nframes = params[:4]
        print(f"Audio params: channels={nchannels}, width={sampwidth}, rate={framerate}, frames={nframes}")
        data = w.readframes(nframes)
        
    # parse as short integers (16-bit)
    samples = struct.unpack(f"<{nframes}h", data)
    
    # Analyze in 1-second chunks
    chunk_size = framerate
    total_seconds = nframes // framerate
    print(f"Total duration: {total_seconds} seconds")
    for sec in range(total_seconds):
        chunk = samples[sec*chunk_size : (sec+1)*chunk_size]
        if not chunk:
            continue
        rms = (sum(s**2 for s in chunk) / len(chunk)) ** 0.5
        # Print RMS amplitude. Dead silence is 0 or close to 0.
        status = "SILENT" if rms < 50 else "ACTIVE"
        print(f"Second {sec:02d}: RMS = {rms:.2f} ({status})")
        
    # Cleanup
    try:
        os.remove(wav_path)
    except:
        pass

if __name__ == "__main__":
    main()
