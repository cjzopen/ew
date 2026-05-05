import os
import requests
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("YOUTUBE_DATA_API_KEY")
CHANNEL_HANDLES = ["@DATASYStw", "@DigiwinsoftASEAN"]

def parse_duration_seconds(duration_str):
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

def get_all_videos(api_key, playlist_id, handle):
    print("Fetching all videos from the channel...")
    video_ids = []
    page_token = ""
    
    while True:
        url = f"https://youtube.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId={playlist_id}&maxResults=50&key={api_key}"
        if page_token:
            url += f"&pageToken={page_token}"
            
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        
        stop_fetching = False
        for item in data.get('items', []):
            pub_date = item['snippet']['publishedAt']
            if pub_date < "2023-01-03T00:00:00Z":
                stop_fetching = True
                continue
            video_ids.append(item['snippet']['resourceId']['videoId'])
            
        if stop_fetching:
            break
            
        page_token = data.get('nextPageToken')
        if not page_token:
            break
            
    print(f"Found {len(video_ids)} videos in total.")
    
    # Process in chunks of 50
    final_videos = []
    
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        ids_param = ",".join(chunk)
        details_url = f"https://youtube.googleapis.com/youtube/v3/videos?part=snippet,contentDetails,statistics&id={ids_param}&key={api_key}"
        details_resp = requests.get(details_url)
        details_resp.raise_for_status()
        details_data = details_resp.json()
        
        for item in details_data.get('items', []):
            vid = item['id']
            title = item['snippet'].get('title', '')
            description = item['snippet'].get('description', '')
            pub_date = item['snippet'].get('publishedAt', '')[:10]  # Get YYYY-MM-DD
            duration_str = item['contentDetails'].get('duration', 'PT0S')
            duration_sec = parse_duration_seconds(duration_str)
            
            stats = item.get('statistics', {})
            views = stats.get('viewCount', '0')
            likes = stats.get('likeCount', '0')
            comments = stats.get('commentCount', '0')
            
            # Filter out shorts
            # YouTube Shorts can now be up to 3 minutes (180s) long
            is_short = False
            if duration_sec <= 190:
                try:
                    head_resp = requests.head(f"https://www.youtube.com/shorts/{vid}", allow_redirects=False, timeout=5)
                    if head_resp.status_code != 303:
                        is_short = True
                except Exception:
                    pass
            
            if not is_short:
                final_videos.append({
                    'id': vid,
                    'title': title,
                    'description': description,
                    'pub_date': pub_date,
                    'views': views,
                    'likes': likes,
                    'comments': comments,
                    'handle': handle
                })
                
        print(f"Processed {min(i+50, len(video_ids))} / {len(video_ids)} videos...")
        
    return final_videos

def generate_html(videos):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # CSS: 使用 CSS 原生的 nest 與變數，並壓縮成一行
    css = ":root{--bg:#f3f4f6;--text:#1f2937;--text-light:#6b7280;--link:#2563eb;--card-bg:#fff;--border:#e5e7eb;--stat-bg:#f8fafc}body{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);margin:0;padding:2rem}h1{text-align:center;font-size:2rem;margin-bottom:0.5rem;color:#111827}.update-time{text-align:center;color:var(--text-light);font-size:0.9rem;margin-bottom:2rem}.filter-bar{text-align:center;margin-bottom:2rem;font-size:1.1rem}.filter-bar select{padding:0.5rem 1rem;font-size:1rem;border-radius:6px;border:1px solid var(--border);margin-left:0.5rem;cursor:pointer;background:#fff}.video-list{max-width:1000px;margin:0 auto;display:flex;flex-direction:column;gap:1rem}.card{background:var(--card-bg);border:1px solid var(--border);border-radius:12px;padding:1.5rem;box-shadow:0 1px 3px rgba(0,0,0,.1);transition:transform .2s}.card:hover{transform:translateY(-2px)}.card-header{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;margin-bottom:1rem}.card-title{margin:0;font-size:1.25rem;font-weight:600;flex:1;line-height:1.4}.card-title a{color:var(--link);text-decoration:none}.card-title a:hover{text-decoration:underline}.stats{display:flex;gap:0.75rem;flex-wrap:wrap}.stat-badge{background:var(--stat-bg);border:1px solid var(--border);border-radius:6px;padding:0.25rem 0.75rem;font-size:0.875rem;font-weight:500;color:var(--text);display:flex;align-items:center;gap:0.25rem}details{background:#f9fafb;border-radius:8px;padding:0.75rem 1rem;border:1px solid #f3f4f6}summary{cursor:pointer;font-weight:500;color:var(--text-light);user-select:none;outline:none}details p{white-space:pre-wrap;font-size:0.9rem;color:#4b5563;margin:0.75rem 0 0;line-height:1.6}"
    
    html = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="nofollow, noindex">
<title>YouTube Channel Dashboard</title>
<style>{css}</style>
</head>
<body>
<h1>Channel Video Dashboard</h1>
<p class="update-time">最後抓取時間：{current_time}</p>
<div class="filter-bar">
  <label for="channelFilter">篩選頻道：</label>
  <select id="channelFilter" onchange="filterChannels()">
    <option value="all">所有頻道 (All)</option>
'''
    for handle in CHANNEL_HANDLES:
        html += f'    <option value="{handle}">{handle}</option>\n'

    html += '''  </select>
</div>
<div class="video-list">
'''
    
    for v in videos:
        title_escaped = v['title'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        desc_escaped = v['description'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        html += f'''  <div class="card" data-channel="{v['handle']}">
    <div class="card-header">
      <h2 class="card-title"><a href="https://www.youtube.com/watch?v={v['id']}" target="_blank">{title_escaped}</a></h2>
      <div class="stats">
        <span class="stat-badge">📅 {v['pub_date']}</span>
        <span class="stat-badge">👁️ {v['views']}</span>
        <span class="stat-badge">👍 {v['likes']}</span>
        <span class="stat-badge">💬 {v['comments']}</span>
      </div>
    </div>
    <details>
      <summary>影片說明 (Description)</summary>
      <p>{desc_escaped}</p>
    </details>
  </div>
'''
        
    html += '''</div>
<script>
function filterChannels() {
  const selected = document.getElementById('channelFilter').value;
  document.querySelectorAll('.card').forEach(card => {
    card.style.display = (selected === 'all' || card.getAttribute('data-channel') === selected) ? 'block' : 'none';
  });
}
</script>
</body>
</html>'''

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Generated index.html successfully.")

def main():
    if not API_KEY:
        print("ERROR: YOUTUBE_DATA_API_KEY not found in .env file.")
        return

    all_channel_videos = []
    try:
        for handle in CHANNEL_HANDLES:
            uploads_playlist_id = get_channel_uploads_playlist(API_KEY, handle)
            videos = get_all_videos(API_KEY, uploads_playlist_id, handle)
            all_channel_videos.extend(videos)
            
        # 全局依日期由新到舊排序
        all_channel_videos.sort(key=lambda x: x.get('pub_date', ''), reverse=True)
            
        generate_html(all_channel_videos)
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
