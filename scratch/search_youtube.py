import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Add parent directory of Proyecto manga recap to python path
base_proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
parent_dir = os.path.dirname(base_proj)
sys.path.append(parent_dir)

from api.youtube_uploader import get_authenticated_service

def search_channel():
    youtube = get_authenticated_service()
    if youtube == "MOCK_SERVICE":
        print("Mock service active.")
        return

    # Search for videos with query
    query = "Aristócrata"
    print(f"Searching for '{query}'...")
    response = youtube.search().list(
        q=query,
        part="snippet",
        maxResults=25,
        type="video",
        forMine=True
    ).execute()

    for item in response.get("items", []):
        title = item["snippet"]["title"]
        video_id = item["id"]["videoId"]
        print(f"FOUND: Title: {title} | Video ID: {video_id}")

if __name__ == "__main__":
    search_channel()
