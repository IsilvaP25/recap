import os
import json

base_proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
manga_name = "A_Single_Aristocrat_Enjoys_a_Different_World_The_Graceful_Life_of_a_Man_Who_Never_Gets_Married"
pub_dir = os.path.join(base_proj, "outputs", manga_name, "FINAL_PUBLICATION")

if not os.path.exists(pub_dir):
    print("Folder does not exist:", pub_dir)
else:
    for folder in sorted(os.listdir(pub_dir)):
        folder_path = os.path.join(pub_dir, folder)
        if os.path.isdir(folder_path):
            print(f"\n--- Folder: {folder} ---")
            files = os.listdir(folder_path)
            print("Files:", files)
            json_file = os.path.join(folder_path, "youtube_data.json")
            if os.path.exists(json_file):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    print("Video ID in JSON:", data.get("video_id"))
                except Exception as e:
                    print("Error reading json:", e)
