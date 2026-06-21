import os
import sys
import json

# Reconfigure stdout to use utf-8
sys.stdout.reconfigure(encoding='utf-8')

# Add parent directory of Proyecto manga recap to python path
base_proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Proyecto manga recap
parent_dir = os.path.dirname(base_proj) # end to end
sys.path.append(parent_dir)

from api.youtube_uploader import get_authenticated_service

def fetch_recent_uploads():
    youtube = get_authenticated_service()
    if youtube == "MOCK_SERVICE":
        print("Mock service active, cannot fetch actual YouTube uploads.")
        return

    # Get uploads playlist ID
    channels_response = youtube.channels().list(
        mine=True,
        part="contentDetails"
    ).execute()
    
    uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    print("Uploads Playlist ID:", uploads_playlist_id)
    
    # List playlist items
    playlistitems_response = youtube.playlistItems().list(
        playlistId=uploads_playlist_id,
        part="snippet",
        maxResults=50
    ).execute()
    
    for item in playlistitems_response.get("items", []):
        title = item["snippet"]["title"]
        video_id = item["snippet"]["resourceId"]["videoId"]
        print(f"Title: {title} | Video ID: {video_id}")

if __name__ == "__main__":
    fetch_recent_uploads()
