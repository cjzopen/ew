# YouTube 字幕抓取升級方案 (OAuth 2.0)

本文件紀錄了後續改寫 YouTube 專案以解決「機器人阻擋 (IP 封鎖) 及 429 錯誤」的 OAuth 2.0 授權方案，供後續開發與討論使用。

## 背景與痛點
目前專案使用的 `youtube-transcript-api` 是基於網頁爬蟲技術。當同一 IP 頻繁請求 YouTube 時，會被官方判定為機器人並遭受暫時性的 IP 封鎖，導致無法抓取字幕。

既然我們已經擁有 Google Cloud Platform 的專案，並且成功建立了 **OAuth 2.0 用戶端 ID**，我們就能改走「官方合法授權」的 API 途徑，徹底擺脫爬蟲被封鎖的困境。

---

## 核心限制與風險評估 (重要)

在決定是否正式動工改寫前，必須先確認以下 YouTube 官方 API 的硬性規定：

1. **僅限人工上傳的字幕**：
   YouTube 官方 Data API (`captions.download`) **嚴格禁止下載「自動產生 (ASR)」的字幕**。若嘗試下載自動辨識的字幕，API 會強制回傳 `403 Forbidden`。
   👉 *評估：如果 DATASYStw 頻道的影片通常是由人工上傳字幕檔 (.srt)，本方案將完美運作。如果是依賴 YouTube 語音自動辨識，則本方案無效，仍得退回爬蟲模式。*

2. **必須是頻道擁有者**：
   透過官方 API 下載字幕時，登入 OAuth 2.0 的 Google 帳號，必須擁有該影片的後台管理權限（頻道擁有者或管理員）。

---

## 預計實作步驟 (Action Plan)

若確認上述限制不成問題，我們將進行以下改寫：

### 1. 準備工作 (需由使用者執行)
1. 進入 Google Cloud Console 的「憑證」頁面。
2. 找到您截圖中的 `youtube-analytics-local` 用戶端 ID。
3. 點擊右側的「下載 JSON」按鈕。
4. 將下載的檔案重新命名為 `client_secret.json`。
5. 將該檔案放入本專案資料夾 (`d:\p\youtube\`) 中。

### 2. 程式碼改寫 (`generate_html.py`)
1. **導入 OAuth 2.0 驗證流程**：
   - 引入 `google-auth-oauthlib`。
   - 程式首次執行時，會自動彈出瀏覽器，要求登入頻道管理員的 Google 帳號並授權。
   - 授權成功後，會在本地端產生 `token.json`，未來執行就不必再重複登入。
   
2. **全面替換為官方 API 客戶端**：
   - 捨棄純粹的 `requests` 呼叫，改用官方的 `googleapiclient.discovery` 套件。
   - `get_channel_uploads_playlist` 與 `get_filtered_latest_videos` 全面改用經過驗證的 client 物件執行。

3. **改寫字幕抓取邏輯 (`get_subtitles`)**：
   - 先透過 `youtube.captions().list(videoId=...)` 取得影片的字幕軌道清單。
   - 尋找繁體中文 (`zh-TW`, `zh-Hant`) 或其他適用語言的 `caption_id`。
   - 透過 `youtube.captions().download(id=caption_id, tfmt="srt")` 正式下載字幕內容。
   - 成功取得後回傳純文字，供後續 HTML 與 Gemini AI 使用。

---

## 替代方案
若頻道多數影片都是依賴「自動產生」的字幕，我們只能放棄 OAuth 2.0 方案。
替代方案為：**維持現狀，並在伺服器端實作 Proxy IP 輪替機制**，或是等待現有 IP 的封鎖自然解除。
