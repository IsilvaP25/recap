import os
import re
import subprocess
import json

def clean_text_for_speech(text):
    # Remove tags and notes
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    # Remove markdown formatting
    text = text.replace("**", "").replace("*", "").replace("__", "").replace("_", "")
    return " ".join(text.split()).strip()

def get_audio_duration(file_path):
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json', 
        '-show_format', '-show_streams', file_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0:
        data = json.loads(result.stdout)
        return float(data['format']['duration'])
    return 0.0

def main():
    script_path = r"c:\Users\ignacio\Desktop\Nueva carpeta (2)\end to end\Proyecto manga recap\outputs\Single_Dad_In_Another_World\Scripts\Short_guion_ESP.txt"
    audio_path = r"c:\Users\ignacio\Desktop\Nueva carpeta (2)\end to end\Proyecto manga recap\outputs\Single_Dad_In_Another_World\_TEMP\Capitulo_1\audio\SHORT_FULL.mp3"
    
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    cleaned = clean_text_for_speech(content)
    words = cleaned.split()
    word_count = len(words)
    
    duration = get_audio_duration(audio_path)
    
    print(f"Original Text: {content}")
    print(f"Cleaned Text: {cleaned}")
    print(f"Word Count: {word_count}")
    print(f"Audio Duration: {duration:.2f} seconds")
    if duration > 0:
        wps = word_count / duration
        wpm = wps * 60
        print(f"Words per second (WPS): {wps:.2f}")
        print(f"Words per minute (WPM): {wpm:.2f}")

if __name__ == "__main__":
    main()
