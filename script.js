const GEMINI_KEY_STORAGE = 'yt_gemini_key';
let geminiKey = '';

function saveApiKey() {
  geminiKey = document.getElementById('geminiKey').value.trim();
  localStorage.setItem(GEMINI_KEY_STORAGE, geminiKey);
}

function simpleHash(str) {
  let h = 0;
  for (let i = 0; i < Math.min(str.length, 600); i++) h = Math.imul(31, h) + str.charCodeAt(i) | 0;
  return (h >>> 0).toString(36);
}

function getCacheKey(vid) {
  const d = VIDEO_DATA[vid];
  return 'yt_score_' + vid + '_' + simpleHash(d.title + d.desc.slice(0, 500) + (d.tags || []).join(','));
}

function checkTimestamps(desc, durationSec) {
  if (durationSec <= 180) return {score: null, tip: null};
  const m = [...desc.matchAll(/\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b/g)];
  if (!m.length) return {score: 0, tip: '影片超過3分鐘，建議在說明中加入時間戳以提升觀眾體驗'};
  const first = m[0];
  const total = first[3] !== undefined
    ? parseInt(first[1]) * 3600 + parseInt(first[2]) * 60 + parseInt(first[3])
    : parseInt(first[1]) * 60 + parseInt(first[2]);
  if (total !== 0) return {score: 5, tip: '第一個時間戳必須從 0:00（或 00:00、0:00:00）開始，才能觸發 YouTube 章節功能'};
  return {score: 10, tip: null};
}

async function callGemini(title, desc, tags) {
  const tagList = (tags || []);
  const tagDisplay = tagList.length > 0 ? tagList.join('、') : '（無）';
  const prompt = `你是 YouTube 頻道內容品質評估專家，專門評估企業軟體教學影片的 AI 友善度。

標題：${title}
說明（前500字）：${desc.slice(0, 500)}
標籤（共 ${tagList.length} 個，以下是完整清單，請勿假設清單以外的標籤存在）：${tagDisplay}

只回傳 JSON，不要其他文字：
{"title_desc_score":數字,"title_desc_tip":"建議或null","tags_score":數字,"tags_tip":"建議或null"}

評分標準（嚴格）：
- 標題＋說明（0~70分）：主題具體性、是否說明產品名稱／功能／使用情境、觀眾能否快速判斷值不值得看、AI 能否充分理解影片在教什麼
- 標籤（0~20分）：只根據上方提供的實際標籤清單評分，與內容相關性、有無具體產品名與功能關鍵字、是否過於籠統或缺漏

tip 若無建議填 null，否則一句繁體中文改善建議。`;

  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key=${geminiKey}`,
    {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        contents: [{parts: [{text: prompt}]}],
        generationConfig: {responseMimeType: 'application/json', temperature: 1.0}
      })
    }
  );
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error?.message || 'Gemini API 錯誤');
  }
  const data = await res.json();
  return JSON.parse(data.candidates[0].content.parts[0].text);
}

function scoreColor(s) {
  return s >= 80 ? '#34c759' : s >= 60 ? '#ff9500' : '#ff3b30';
}

function renderScore(vid, r) {
  const tsScore = r.timestamps_score ?? 10;
  const total = (r.title_desc_score || 0) + (r.tags_score || 0) + tsScore;
  const card = document.querySelector(`.card[data-id="${vid}"]`);
  if (card) card.dataset.score = total;

  const badge = document.getElementById('score-' + vid);
  if (badge) {
    badge.style.display = '';
    badge.style.background = scoreColor(total);
    badge.textContent = '★ ' + total;
  }

  const tips = document.getElementById('tips-' + vid);
  if (!tips) return;
  const tsLabel = r.timestamps_score === null ? '不適用' : r.timestamps_score + ' / 10';
  const rows = [
    ['標題＋說明', (r.title_desc_score || 0) + ' / 70', r.title_desc_tip],
    ['標籤', (r.tags_score || 0) + ' / 20', r.tags_tip],
    ['時間戳', tsLabel, r.timestamps_tip],
  ];
  tips.style.display = '';
  tips.innerHTML = `<div class="score-total" style="color:${scoreColor(total)}">綜合評分 ${total} / 100</div>`
    + rows.map(([dim, val, tip]) =>
      `<div class="score-row"><span class="score-dim">${dim}</span><span class="score-val">${val}</span>${tip ? `<span class="score-tip">→ ${tip}</span>` : ''}</div>`
    ).join('');
}

function loadCachedScore(vid) {
  const cached = localStorage.getItem(getCacheKey(vid));
  if (!cached) return;
  renderScore(vid, JSON.parse(cached));
  const btn = document.getElementById('btn-' + vid);
  if (btn) btn.textContent = '重新分析';
}

async function analyzeVideo(vid) {
  const key = geminiKey || localStorage.getItem(GEMINI_KEY_STORAGE) || '';
  if (!key) {
    alert('請先在上方輸入 Gemini API Key');
    document.getElementById('geminiKey')?.focus();
    return;
  }
  geminiKey = key;
  const btn = document.getElementById('btn-' + vid);
  btn.disabled = true;
  btn.textContent = '分析中…';
  try {
    const d = VIDEO_DATA[vid];
    const [geminiResult, tsResult] = await Promise.all([
      callGemini(d.title, d.desc, d.tags),
      Promise.resolve(checkTimestamps(d.desc, d.duration))
    ]);
    const result = {
      title_desc_score: geminiResult.title_desc_score || 0,
      title_desc_tip: geminiResult.title_desc_tip === 'null' ? null : geminiResult.title_desc_tip,
      tags_score: geminiResult.tags_score || 0,
      tags_tip: geminiResult.tags_tip === 'null' ? null : geminiResult.tags_tip,
      timestamps_score: tsResult.score,
      timestamps_tip: tsResult.tip
    };
    localStorage.setItem(getCacheKey(vid), JSON.stringify(result));
    renderScore(vid, result);
    btn.textContent = '重新分析';
  } catch(e) {
    alert('分析失敗：' + e.message);
    btn.textContent = 'AI 分析';
  } finally {
    btn.disabled = false;
  }
}

(function init() {
  const saved = localStorage.getItem(GEMINI_KEY_STORAGE);
  if (saved) { document.getElementById('geminiKey').value = saved; geminiKey = saved; }
  document.querySelectorAll('.card[data-id]').forEach(c => loadCachedScore(c.dataset.id));
})();

const activeSorts = [{key:"date",desc:true}];

function toggleSort(btn) {
  const key = btn.dataset.sort;
  const idx = activeSorts.findIndex(s => s.key === key);
  if (idx > -1) {
    if (activeSorts[idx].desc) activeSorts[idx].desc = false;
    else activeSorts.splice(idx, 1);
  } else {
    activeSorts.push({key, desc: true});
  }
  updatePillUI();
  applyFilters();
}

function updatePillUI() {
  document.querySelectorAll(".sort-pill").forEach(pill => {
    const key = pill.dataset.sort;
    const s = activeSorts.find(x => x.key === key);
    pill.classList.toggle("active", !!s);
    pill.querySelector(".arrow").textContent = s ? (s.desc ? "↓" : "↑") : "↓";
  });
}

function applyFilters() {
  const channel = document.getElementById("channelFilter").value;
  const list = document.getElementById("videoList");
  const cards = [...list.querySelectorAll(".card")];
  cards.forEach(c => c.style.display = (channel === "all" || c.dataset.channel === channel) ? "" : "none");
  if (activeSorts.length > 0) {
    cards.sort((a, b) => {
      for (const {key, desc} of activeSorts) {
        let va, vb;
        if (key === "date") { va = a.dataset.date; vb = b.dataset.date; }
        else if (key === "views") { va = +a.dataset.views; vb = +b.dataset.views; }
        else if (key === "likes") { va = +a.dataset.likes; vb = +b.dataset.likes; }
        else if (key === "comments") { va = +a.dataset.comments; vb = +b.dataset.comments; }
        else if (key === "duration") { va = +a.dataset.duration; vb = +b.dataset.duration; }
        else if (key === "score") { va = a.dataset.score ? +a.dataset.score : -1; vb = b.dataset.score ? +b.dataset.score : -1; }
        const cmp = va < vb ? -1 : va > vb ? 1 : 0;
        if (cmp !== 0) return desc ? -cmp : cmp;
      }
      return 0;
    });
    cards.forEach(c => list.appendChild(c));
  }
}