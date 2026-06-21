import os
import sys

# Reconfigure stdout to use utf-8
sys.stdout.reconfigure(encoding='utf-8')

# Add parent directory of Proyecto manga recap to python path
base_proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
parent_dir = os.path.dirname(base_proj)
sys.path.append(parent_dir)

from api.youtube_uploader import get_authenticated_service

def find_long_videos():
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
    found_videos = []
    
    while page <= 10:  # Check up to 500 uploads
        print(f"Fetching page {page}...")
        playlistitems_response = youtube.playlistItems().list(
            playlistId=uploads_playlist_id,
            part="snippet",
            maxResults=50,
            pageToken=next_page_token
        ).execute()
        
        for item in playlistitems_response.get("items", []):
            title = item["snippet"]["title"]
            video_id = item["snippet"]["resourceId"]["videoId"]
            
            # Look for titles containing "Soltero Aristócrata" or "Aristócrata" or matching the parts
            if "arist" in title.lower() or "soltero" in title.lower():
                found_videos.append((title, video_id))
                print(f"FOUND: Title: {title} | Video ID: {video_id}")
                
        next_page_token = playlistitems_response.get("nextPageToken")
        if not next_page_token:
            break
        page += 1

    print("\n--- Summary of Found Videos ---")
    for t, vid in found_videos:
        print(f"Title: {t} | ID: {vid}")

if __name__ == "__main__":
    find_long_videos()
