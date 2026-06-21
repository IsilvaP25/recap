import os
import sys

# Reconfigure stdout to use utf-8
sys.stdout.reconfigure(encoding='utf-8')

# Add parent directory of Proyecto manga recap to python path
base_proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
parent_dir = os.path.dirname(base_proj)
sys.path.append(parent_dir)

from api.youtube_uploader import get_authenticated_service

def list_all_videos():
    youtube = get_authenticated_service()
    if youtube == "MOCK_SERVICE":
        print("Mock service active.")
        return

    channels_response = youtube.channels().list(
        mine=True,
        part="contentDetails"
    ).execute()
    
    uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    
    next_page_token = None
    page = 1
    
    with open("scratch/all_videos.txt", "w", encoding="utf-8") as f:
        while True:
            playlistitems_response = youtube.playlistItems().list(
                playlistId=uploads_playlist_id,
                part="snippet",
                maxResults=50,
                pageToken=next_page_token
            ).execute()
            
            items = playlistitems_response.get("items", [])
            if not items:
                break
                
            for item in items:
                title = item["snippet"]["title"]
                video_id = item["snippet"]["resourceId"]["videoId"]
                f.write(f"ID: {video_id} | Title: {title}\n")
                
            next_page_token = playlistitems_response.get("nextPageToken")
            if not next_page_token:
                break
            page += 1
            
    print(f"Finished writing all videos to scratch/all_videos.txt. Total pages fetched: {page}")

if __name__ == "__main__":
    list_all_videos()
