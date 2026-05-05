import os
import json
import requests
import re
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

# Load API key from .env
load_dotenv()
API_KEY = os.getenv("YOUTUBE_DATA_API_KEY")

CHANNEL_HANDLE = "@DATASYStw"
MAX_VIDEOS = 5

# Rules for duration filtering
MAX_VIDEO_DURATION_SECONDS = 3600  # 1 hour (ignore longer videos)
MAX_SUBTITLE_DURATION_SECONDS = 1200 # 20 minutes (skip subtitles if longer)

def parse_duration_seconds(duration_str):
    # Parses ISO 8601 duration (e.g., PT1H5M30S)
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return 0
    h = int(match.group(1)) if match.group(1) else 0
    m = int(match.group(2)) if match.group(2) else 0
    s = int(match.group(3)) if match.group(3) else 0
    return h * 3600 + m * 60 + s

def get_channel_uploads_playlist(api_key, handle):
    print(f"Fetching channel info for {handle}...")
    url = f"https://youtube.googleapis.com/youtube/v3/channels?part=contentDetails&forHandle={handle}&key={api_key}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    
    if not data.get('items'):
        raise Exception(f"Could not find channel for handle {handle}")
        
    return data['items'][0]['contentDetails']['relatedPlaylists']['uploads']

def get_filtered_latest_videos(api_key, playlist_id):
    print("Fetching recent videos and checking durations/shorts...")
    # Fetch 50 recent videos
    url = f"https://youtube.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId={playlist_id}&maxResults=50&key={api_key}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    
    raw_video_ids = [item['snippet']['resourceId']['videoId'] for item in data.get('items', [])]
    
    if not raw_video_ids:
        return []

    # Get details (including duration) for all 50 videos in one call
    ids_param = ",".join(raw_video_ids)
    details_url = f"https://youtube.googleapis.com/youtube/v3/videos?part=snippet,contentDetails&id={ids_param}&key={api_key}"
    details_resp = requests.get(details_url)
    details_resp.raise_for_status()
    details_data = details_resp.json()
    
    # Map video details by ID for easy lookup
    video_map = {}
    for item in details_data.get('items', []):
        vid = item['id']
        video_map[vid] = {
            'title': item['snippet'].get('title', ''),
            'description': item['snippet'].get('description', ''),
            'duration_str': item['contentDetails'].get('duration', 'PT0S')
        }

    final_videos = []
    
    # Iterate through the original order to keep latest first
    for vid in raw_video_ids:
        if vid not in video_map:
            continue
            
        details = video_map[vid]
        duration_sec = parse_duration_seconds(details['duration_str'])
        
        # 1. Filter out videos longer than 1 hour
        if duration_sec > MAX_VIDEO_DURATION_SECONDS:
            continue
            
        # 2. Filter out shorts
        try:
            head_resp = requests.head(f"https://www.youtube.com/shorts/{vid}", allow_redirects=False, timeout=5)
            if head_resp.status_code != 303:
                continue # It's a short (returns 200)
        except Exception:
            pass # Ignore errors and assume it's regular if head fails
            
        # Add to final list
        details['id'] = vid
        details['duration_sec'] = duration_sec
        final_videos.append(details)
        
        if len(final_videos) >= MAX_VIDEOS:
            break
            
    return final_videos

def get_subtitles(video_id):
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id, languages=['zh-TW', 'zh-Hant', 'zh', 'en'])
        formatter = TextFormatter()
        return formatter.format_transcript(transcript)
    except Exception as e:
        print(f"No subtitles found for {video_id} ({e})")
        return ""

def main():
    if not API_KEY:
        print("ERROR: YOUTUBE_DATA_API_KEY not found in .env file.")
        return

    try:
        uploads_playlist_id = get_channel_uploads_playlist(API_KEY, CHANNEL_HANDLE)
        videos_to_process = get_filtered_latest_videos(API_KEY, uploads_playlist_id)
        
        video_data_list = []
        for idx, video in enumerate(videos_to_process):
            vid = video['id']
            duration_sec = video['duration_sec']
            print(f"Processing ({idx+1}/{len(videos_to_process)}): {vid} (Duration: {duration_sec}s)")
            
            # Subtitle token limit rule: skip if longer than 20 minutes
            if duration_sec > MAX_SUBTITLE_DURATION_SECONDS:
                print(f" -> Skipping subtitles (video > 20 mins)")
                subtitles = "影片超過20分鐘，系統設定不抓取字幕以節省 Token。"
            else:
                subtitles = get_subtitles(vid)
            
            video_data_list.append({
                'id': vid,
                'title': video['title'],
                'description': video['description'],
                'subtitles': subtitles
            })

        # Generate HTML
        with open('template.html', 'r', encoding='utf-8') as f:
            template = f.read()
            
        html_content = template.replace('{{VIDEO_DATA}}', json.dumps(video_data_list, ensure_ascii=False))
        
        with open('ai.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print("Done! Generated ai.html")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
