import os
import json
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

def format_duration(seconds):
  h = seconds // 3600
  m = (seconds % 3600) // 60
  s = seconds % 60
  if h > 0:
    return f"{h}:{m:02d}:{s:02d}"
  return f"{m}:{s:02d}"

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
      tags = item['snippet'].get('tags', [])
      pub_date = item['snippet'].get('publishedAt', '')[:10]
      duration_str = item['contentDetails'].get('duration', 'PT0S')
      duration_sec = parse_duration_seconds(duration_str)

      stats = item.get('statistics', {})
      views = stats.get('viewCount', '0')
      likes = stats.get('likeCount', '0')
      comments = stats.get('commentCount', '0')

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
          'tags': tags,
          'pub_date': pub_date,
          'duration_sec': duration_sec,
          'duration_str': format_duration(duration_sec),
          'views': views,
          'likes': likes,
          'comments': comments,
          'handle': handle
        })

    print(f"Processed {min(i+50, len(video_ids))} / {len(video_ids)} videos...")

  return final_videos

def generate_html(videos):
  current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

  video_data = {v['id']: {
    'title': v['title'],
    'desc': v['description'],
    'tags': v.get('tags', []),
    'duration': v['duration_sec']
  } for v in videos}

  svg = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%2386868b'/%3E%3C/svg%3E"
  css = (
    ":root{--text:#1d1d1f;--bg:#f5f5f7;--link:#0071e3;--card-bg:#fff"
    ";--text-s:color-mix(in srgb,var(--text) 47%,#fff)"
    ";--pill-bg:color-mix(in srgb,var(--text) 4%,transparent)"
    ";--shadow:0 2px 12px rgba(0,0,0,.08);--radius:16px"
    ";--font:-apple-system,BlinkMacSystemFont,'SF Pro Display','SF Pro Text','Helvetica Neue',sans-serif}"
    "*{box-sizing:border-box;margin:0;padding:0}"
    ":where(body){font-family:var(--font);background-color:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}"
    ".container{max-width:980px;margin:0 auto;padding:3rem 1.5rem 4rem}"
    ".page-header{text-align:center;margin-bottom:2.5rem;& :where(h1){font-size:2.5rem;font-weight:700;letter-spacing:-.02em;color:var(--text);margin-bottom:.5rem}}"
    ".update-time{font-size:.85rem;color:var(--text-s);font-weight:400}"
    ".toolbar{display:flex;flex-wrap:wrap;gap:.75rem;align-items:center;justify-content:center;margin-bottom:2rem;padding:1rem 1.25rem"
    ";background-color:var(--card-bg);border-radius:var(--radius);box-shadow:var(--shadow)"
    ";& :where(select){appearance:none;-webkit-appearance:none;padding:.5rem 2rem .5rem .75rem;font-size:.85rem;font-family:var(--font);font-weight:500"
    ";border:1.5px solid rgba(0,0,0,.12);border-radius:10px;background-color:#fff"
    f";background-image:url('{svg}');background-repeat:no-repeat;background-position:right .75rem center"
    ";cursor:pointer;color:var(--text);transition:border-color .2s"
    ";&:focus{outline:none;border-color:var(--link);box-shadow:0 0 0 3px color-mix(in srgb,var(--link) 15%,transparent)}}}"
    ".toolbar-group{display:flex;align-items:center;gap:.5rem}"
    ".toolbar-label{font-size:.8rem;font-weight:600;color:var(--text-s);text-transform:uppercase;letter-spacing:.05em;white-space:nowrap}"
    ".sort-pills{display:flex;flex-wrap:wrap;gap:.375rem}"
    ".sort-pill{display:inline-flex;align-items:center;gap:.25rem;padding:.4rem .75rem;font-size:.8rem;font-weight:500;font-family:var(--font)"
    ";border:1.5px solid rgba(0,0,0,.1);border-radius:20px;background-color:transparent;color:var(--text)"
    ";cursor:pointer;transition:all .2s ease;user-select:none;white-space:nowrap"
    ";&:hover{background-color:var(--pill-bg);border-color:rgba(0,0,0,.2)}"
    ";&.active{background-color:var(--text);color:var(--card-bg);border-color:var(--text)}"
    ";& .arrow{font-size:.7rem;opacity:.7}}"
    ".video-list{display:flex;flex-direction:column;gap:.75rem}"
    ".card{background-color:var(--card-bg);border-radius:var(--radius);padding:1.25rem 1.5rem"
    ";box-shadow:var(--shadow);transition:transform .25s cubic-bezier(.25,.46,.45,.94),box-shadow .25s ease"
    ";&:hover{transform:translateY(-2px);box-shadow:0 4px 20px rgba(0,0,0,.12)}}"
    ".card-header{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;margin-bottom:.75rem}"
    ".card-title{margin:0;font-size:1.1rem;font-weight:600;line-height:1.4;letter-spacing:-.01em"
    ";flex-grow:1;flex-shrink:1;flex-basis:0%"
    ";& :where(a){color:var(--text);text-decoration:none;transition:color .2s;&:hover{color:var(--link)}}}"
    ".stats{display:flex;gap:.5rem;flex-wrap:wrap;flex-shrink:0}"
    ".stat-badge{display:inline-flex;align-items:center;gap:.3rem;padding:.3rem .65rem;font-size:.75rem;font-weight:500;color:var(--text-s);background-color:var(--pill-bg);border-radius:8px;white-space:nowrap}"
    ":where(details){border-radius:10px;padding:.6rem .85rem;background-color:color-mix(in srgb,var(--text) 2%,transparent)"
    ";& :where(p){white-space:pre-wrap;font-size:.85rem;color:var(--text-s);margin:.75rem 0 .25rem;line-height:1.65}}"
    ":where(summary){cursor:pointer;font-weight:500;font-size:.85rem;color:var(--text-s);user-select:none;outline:none;list-style:none"
    ";&::before{content:'+';display:inline-block;width:1.2em;font-weight:300;font-size:1.1rem;transition:transform .2s}}"
    ":where(details[open]) :where(summary)::before{content:'-'}"
    ".api-key-input{flex:1;min-width:160px;max-width:300px;padding:8px 12px;font-size:.85rem;font-family:var(--font);color:#1d1d1f;background:#fff;border:1.5px solid #d2d2d7;border-radius:10px;outline:none;transition:border-color .2s,box-shadow .2s;&:focus{border-color:#0071e3;box-shadow:0 0 0 3px rgba(0,113,227,.15)}}"
    ".analyze-btn{background:#0071e3;color:#fff;border:none;border-radius:980px;padding:7px 16px;font-size:.78rem;font-weight:600;font-family:var(--font);cursor:pointer;transition:background .2s,opacity .2s;white-space:nowrap;&:hover{background:#0077ed};&:disabled{opacity:.45;cursor:default}}"
    ".score-badge{display:inline-flex;align-items:center;padding:.28rem .65rem;font-size:.72rem;font-weight:700;border-radius:7px;color:#fff;white-space:nowrap}"
    ".card-footer{display:flex;justify-content:flex-end;margin-top:.85rem}"
    ".ai-tips{margin-top:.75rem;padding:.85rem 1rem;background:#f5f5f7;border-radius:10px;display:flex;flex-direction:column;gap:.4rem}"
    ".score-total{font-size:.88rem;font-weight:700;margin-bottom:.15rem}"
    ".score-row{display:flex;align-items:baseline;flex-wrap:wrap;gap:.4rem}"
    ".score-dim{font-size:.78rem;font-weight:600;color:#1d1d1f;min-width:76px}"
    ".score-val{font-size:.78rem;font-weight:700;color:#0071e3;min-width:42px}"
    ".score-tip{font-size:.78rem;color:#6e6e73;flex:1}"
    "@media(max-width:640px){.container{padding:1.5rem 1rem 3rem}.page-header :where(h1){font-size:1.75rem}"
    ".card-header{flex-direction:column;gap:.5rem}.stats{justify-content:flex-start}"
    ".toolbar{flex-direction:column;align-items:stretch}.toolbar-group{justify-content:center}}"
  )

  vd_json = json.dumps(video_data, ensure_ascii=False)

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
<div class="container">
  <header class="page-header">
    <h1>Channel Dashboard</h1>
    <p class="update-time">最後更新：{current_time}</p>
  </header>

  <nav class="toolbar">
    <div class="toolbar-group">
      <span class="toolbar-label">頻道</span>
      <select id="channelFilter" onchange="applyFilters()">
        <option value="all">全部</option>
'''
  for handle in CHANNEL_HANDLES:
    html += f'        <option value="{handle}">{handle}</option>\n'

  html += '''      </select>
    </div>
    <div class="toolbar-group">
      <span class="toolbar-label">排序</span>
      <div class="sort-pills">
        <button class="sort-pill active" data-sort="date" onclick="toggleSort(this)">日期 <span class="arrow">↓</span></button>
        <button class="sort-pill" data-sort="views" onclick="toggleSort(this)">觀看 <span class="arrow">↓</span></button>
        <button class="sort-pill" data-sort="likes" onclick="toggleSort(this)">按讚 <span class="arrow">↓</span></button>
        <button class="sort-pill" data-sort="comments" onclick="toggleSort(this)">留言 <span class="arrow">↓</span></button>
        <button class="sort-pill" data-sort="duration" onclick="toggleSort(this)">片長 <span class="arrow">↓</span></button>
        <button class="sort-pill" data-sort="score" onclick="toggleSort(this)">分數 <span class="arrow">↓</span></button>
      </div>
    </div>
    <div class="toolbar-group">
      <span class="toolbar-label">Gemini</span>
      <input class="api-key-input" id="geminiKey" type="password" placeholder="輸入 API Key" oninput="saveApiKey()">
    </div>
  </nav>

  <div class="video-list" id="videoList">
'''

  for v in videos:
    te = v['title'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    de = v['description'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    html += f'''    <div class="card" data-id="{v['id']}" data-channel="{v['handle']}" data-date="{v['pub_date']}" data-views="{v['views']}" data-likes="{v['likes']}" data-comments="{v['comments']}" data-duration="{v['duration_sec']}" data-score="">
      <div class="card-header">
        <h2 class="card-title"><a href="https://www.youtube.com/watch?v={v['id']}" target="_blank">{te}</a></h2>
        <div class="stats">
          <span class="stat-badge">📅 {v['pub_date']}</span>
          <span class="stat-badge">⏱ {v['duration_str']}</span>
          <span class="stat-badge">▶ {int(v['views']):,}</span>
          <span class="stat-badge">👍 {int(v['likes']):,}</span>
          <span class="stat-badge">💬 {int(v['comments']):,}</span>
          <span class="score-badge" id="score-{v['id']}" style="display:none"></span>
        </div>
      </div>
      <details>
        <summary>影片說明</summary>
        <p>{de}</p>
      </details>
      <div class="ai-tips" id="tips-{v['id']}" style="display:none"></div>
      <div class="card-footer">
        <button class="analyze-btn" id="btn-{v['id']}" onclick="analyzeVideo('{v['id']}')">AI 分析</button>
      </div>
    </div>
'''

  html += f'''  </div>
</div>
<script>
const VIDEO_DATA = {vd_json};
const GEMINI_KEY_STORAGE = 'yt_gemini_key';
let geminiKey = '';

function saveApiKey() {{
  geminiKey = document.getElementById('geminiKey').value.trim();
  localStorage.setItem(GEMINI_KEY_STORAGE, geminiKey);
}}

function simpleHash(str) {{
  let h = 0;
  for (let i = 0; i < Math.min(str.length, 600); i++) h = Math.imul(31, h) + str.charCodeAt(i) | 0;
  return (h >>> 0).toString(36);
}}

function getCacheKey(vid) {{
  const d = VIDEO_DATA[vid];
  return 'yt_score_' + vid + '_' + simpleHash(d.title + d.desc.slice(0, 500) + (d.tags || []).join(','));
}}

function checkTimestamps(desc, durationSec) {{
  if (durationSec <= 180) return {{score: null, tip: null}};
  const m = [...desc.matchAll(/\\b(\\d{{1,2}}):(\\d{{2}})(?::(\\d{{2}}))?\\b/g)];
  if (!m.length) return {{score: 0, tip: '影片超過3分鐘，建議在說明中加入時間戳以提升觀眾體驗'}};
  const first = m[0];
  const total = first[3] !== undefined
    ? parseInt(first[1]) * 3600 + parseInt(first[2]) * 60 + parseInt(first[3])
    : parseInt(first[1]) * 60 + parseInt(first[2]);
  if (total !== 0) return {{score: 5, tip: '第一個時間戳必須從 0:00（或 00:00、0:00:00）開始，才能觸發 YouTube 章節功能'}};
  return {{score: 10, tip: null}};
}}

async function callGemini(title, desc, tags) {{
  const prompt = `你是 YouTube 頻道內容品質評估專家，專門評估企業軟體教學影片的 AI 友善度。

標題：${{title}}
說明（前500字）：${{desc.slice(0, 500)}}
標籤：${{(tags || []).join('、') || '（無）'}}

只回傳 JSON，不要其他文字：
{{"title_desc_score":數字,"title_desc_tip":"建議或null","tags_score":數字,"tags_tip":"建議或null"}}

評分標準（嚴格）：
- 標題＋說明（0~70分）：主題具體性、是否說明產品名稱／功能／使用情境、觀眾能否快速判斷值不值得看、AI 能否充分理解影片在教什麼
- 標籤（0~20分）：與內容相關性、有無具體產品名與功能關鍵字、是否過於籠統或缺漏

tip 若無建議填 null，否則一句繁體中文改善建議。`;

  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key=${{geminiKey}}`,
    {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        contents: [{{parts: [{{text: prompt}}]}}],
        generationConfig: {{responseMimeType: 'application/json', temperature: 0.2}}
      }})
    }}
  );
  if (!res.ok) {{
    const err = await res.json();
    throw new Error(err.error?.message || 'Gemini API 錯誤');
  }}
  const data = await res.json();
  return JSON.parse(data.candidates[0].content.parts[0].text);
}}

function scoreColor(s) {{
  return s >= 80 ? '#34c759' : s >= 60 ? '#ff9500' : '#ff3b30';
}}

function renderScore(vid, r) {{
  const tsScore = r.timestamps_score ?? 10;
  const total = (r.title_desc_score || 0) + (r.tags_score || 0) + tsScore;
  const card = document.querySelector(`.card[data-id="${{vid}}"]`);
  if (card) card.dataset.score = total;

  const badge = document.getElementById('score-' + vid);
  if (badge) {{
    badge.style.display = '';
    badge.style.background = scoreColor(total);
    badge.textContent = '★ ' + total;
  }}

  const tips = document.getElementById('tips-' + vid);
  if (!tips) return;
  const tsLabel = r.timestamps_score === null ? '不適用' : r.timestamps_score + ' / 10';
  const rows = [
    ['標題＋說明', (r.title_desc_score || 0) + ' / 70', r.title_desc_tip],
    ['標籤', (r.tags_score || 0) + ' / 20', r.tags_tip],
    ['時間戳', tsLabel, r.timestamps_tip],
  ];
  tips.style.display = '';
  tips.innerHTML = `<div class="score-total" style="color:${{scoreColor(total)}}">綜合評分 ${{total}} / 100</div>`
    + rows.map(([dim, val, tip]) =>
      `<div class="score-row"><span class="score-dim">${{dim}}</span><span class="score-val">${{val}}</span>${{tip ? `<span class="score-tip">→ ${{tip}}</span>` : ''}}</div>`
    ).join('');
}}

function loadCachedScore(vid) {{
  const cached = localStorage.getItem(getCacheKey(vid));
  if (!cached) return;
  renderScore(vid, JSON.parse(cached));
  const btn = document.getElementById('btn-' + vid);
  if (btn) btn.textContent = '重新分析';
}}

async function analyzeVideo(vid) {{
  const key = geminiKey || localStorage.getItem(GEMINI_KEY_STORAGE) || '';
  if (!key) {{
    alert('請先在上方輸入 Gemini API Key');
    document.getElementById('geminiKey')?.focus();
    return;
  }}
  geminiKey = key;
  const btn = document.getElementById('btn-' + vid);
  btn.disabled = true;
  btn.textContent = '分析中…';
  try {{
    const d = VIDEO_DATA[vid];
    const [geminiResult, tsResult] = await Promise.all([
      callGemini(d.title, d.desc, d.tags),
      Promise.resolve(checkTimestamps(d.desc, d.duration))
    ]);
    const result = {{
      title_desc_score: geminiResult.title_desc_score || 0,
      title_desc_tip: geminiResult.title_desc_tip === 'null' ? null : geminiResult.title_desc_tip,
      tags_score: geminiResult.tags_score || 0,
      tags_tip: geminiResult.tags_tip === 'null' ? null : geminiResult.tags_tip,
      timestamps_score: tsResult.score,
      timestamps_tip: tsResult.tip
    }};
    localStorage.setItem(getCacheKey(vid), JSON.stringify(result));
    renderScore(vid, result);
    btn.textContent = '重新分析';
  }} catch(e) {{
    alert('分析失敗：' + e.message);
    btn.textContent = 'AI 分析';
  }} finally {{
    btn.disabled = false;
  }}
}}

(function init() {{
  const saved = localStorage.getItem(GEMINI_KEY_STORAGE);
  if (saved) {{ document.getElementById('geminiKey').value = saved; geminiKey = saved; }}
  document.querySelectorAll('.card[data-id]').forEach(c => loadCachedScore(c.dataset.id));
}})();

const activeSorts = [{{key:"date",desc:true}}];

function toggleSort(btn) {{
  const key = btn.dataset.sort;
  const idx = activeSorts.findIndex(s => s.key === key);
  if (idx > -1) {{
    if (activeSorts[idx].desc) activeSorts[idx].desc = false;
    else activeSorts.splice(idx, 1);
  }} else {{
    activeSorts.push({{key, desc: true}});
  }}
  updatePillUI();
  applyFilters();
}}

function updatePillUI() {{
  document.querySelectorAll(".sort-pill").forEach(pill => {{
    const key = pill.dataset.sort;
    const s = activeSorts.find(x => x.key === key);
    pill.classList.toggle("active", !!s);
    pill.querySelector(".arrow").textContent = s ? (s.desc ? "↓" : "↑") : "↓";
  }});
}}

function applyFilters() {{
  const channel = document.getElementById("channelFilter").value;
  const list = document.getElementById("videoList");
  const cards = [...list.querySelectorAll(".card")];
  cards.forEach(c => c.style.display = (channel === "all" || c.dataset.channel === channel) ? "" : "none");
  if (activeSorts.length > 0) {{
    cards.sort((a, b) => {{
      for (const {{key, desc}} of activeSorts) {{
        let va, vb;
        if (key === "date") {{ va = a.dataset.date; vb = b.dataset.date; }}
        else if (key === "views") {{ va = +a.dataset.views; vb = +b.dataset.views; }}
        else if (key === "likes") {{ va = +a.dataset.likes; vb = +b.dataset.likes; }}
        else if (key === "comments") {{ va = +a.dataset.comments; vb = +b.dataset.comments; }}
        else if (key === "duration") {{ va = +a.dataset.duration; vb = +b.dataset.duration; }}
        else if (key === "score") {{ va = a.dataset.score ? +a.dataset.score : -1; vb = b.dataset.score ? +b.dataset.score : -1; }}
        const cmp = va < vb ? -1 : va > vb ? 1 : 0;
        if (cmp !== 0) return desc ? -cmp : cmp;
      }}
      return 0;
    }});
    cards.forEach(c => list.appendChild(c));
  }}
}}
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

    all_channel_videos.sort(key=lambda x: x.get('pub_date', ''), reverse=True)
    generate_html(all_channel_videos)
  except Exception as e:
    print(f"An error occurred: {e}")

if __name__ == "__main__":
  main()
