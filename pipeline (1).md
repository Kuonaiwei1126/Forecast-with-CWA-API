# pipeline.md — HW1：利用 CWA 天氣預報網站 using AI Agent

> 課程：人工智慧與資訊安全（NCHU）｜作業：Homework 1
> 作者：郭乃瑋 Leo Kuo｜Repo：https://github.com/Kuonaiwei1126/Forecast-with-CWA-API.git
> 開發環境：VS Code + Claude（取代 Antigravity IDE + Gemini）
> 目標：用自然語言指揮 AI Agent，從 CWA Open Data 取得一週氣溫預報 → 存入 SQLite → 以 Streamlit 建立互動式 Taiwan Weather Forecast 網頁 → 推上 GitHub

---

## 0. 給 AI Agent 的工作守則（請先讀完再動手）

1. **先規劃、再實作**：每個 Phase 先列出要做的事與要產生的檔案，等我確認（或我說「go」）才寫程式。
2. **一次只做一個 Phase**，做完後跑測試、回報結果，再進下一個 Phase。
3. **絕對不要把 API Key 寫死在程式或 commit 進 git**。Key 只放在 `.env`，由 `python-dotenv` 讀取；`.env` 必須在 `.gitignore` 內。
4. 每個 Phase 完成且測試通過後，執行 `git add . && git commit -m "<Phase N>: <說明>" && git push origin main`。
5. 程式碼要求：結構清楚、函式化、有錯誤處理（try/except、HTTP status 檢查）、重複執行不重複插入資料、註解用繁體中文、變數與函式名稱用英文。
6. 遇到任何不確定的地方（資料集代碼、欄位名稱、API 回傳格式）**先用實際 API 回應驗證**，不要憑記憶猜測。
7. 回覆我時使用繁體中文，技術名詞保留英文。

---

## 1. 專案規格

### 1.1 功能需求
| # | 功能 | 說明 |
|---|------|------|
| F1 | 取得 CWA 一週氣溫預報 | 呼叫 CWA Open Data API，取得各地區每日最低溫（MinT）／最高溫（MaxT） |
| F2 | 解析 JSON | 從 `records.locations[].location[].weatherElement[]` 抽出 regionName / dataDate / mint / maxt |
| F3 | 存入 SQLite | 資料表 `TemperatureForecasts`，重複執行不重複插入（UPSERT） |
| F4 | 查詢驗證 | 用 SQL 確認資料筆數、地區清單、日期範圍 |
| F5 | Streamlit Web App | 下拉選單選地區 → 顯示一週 MinT/MaxT 折線圖 + 資料表格 |
| F6 | 台灣地圖（進階） | Folium 地圖，依日期顯示各地區平均氣溫，顏色分級（<20 / 20–25 / 25–30 / >30 °C） |
| F7 | 版本管理 | 全部程式碼推到 GitHub，含 README.md 與使用說明 |

### 1.2 技術棧
- Python 3.11+、`requests`、`python-dotenv`、`pandas`、`sqlite3`（內建）、`streamlit`、`folium`、`streamlit-folium`
- 資料來源：中央氣象署 CWA 開放資料平台 https://opendata.cwa.gov.tw/
  - 主要資料集：**F-D0047-091**（臺灣各縣市一週天氣預報，含 MinT / MaxT）
  - 備援資料集：**F-C0032-001**（36 小時天氣預報）— 若 F-D0047-091 欄位結構與預期不符時改用
- 認證方式：Query string `Authorization=<CWA_API_KEY>`（或 header `Authorization`）

### 1.3 專案結構（AI 請依此建立）
```
Forecast-with-CWA-API/
├── .venv/                 # 虛擬環境（不進 git）
├── .env                   # CWA_API_KEY=...（不進 git）
├── .env.example           # CWA_API_KEY=your_key_here（進 git，給別人參考）
├── .gitignore
├── requirements.txt
├── README.md
├── pipeline.md            # 本檔案
├── data/
│   ├── raw_forecast.json  # API 原始回應（除錯用）
│   └── data.db            # SQLite 資料庫
├── src/
│   ├── __init__.py
│   ├── config.py          # 讀取 .env、常數（URL、dataset id）
│   ├── fetch_cwa.py       # F1：呼叫 API，回傳 dict，並存 raw json
│   ├── parse_forecast.py  # F2：JSON → list[dict] / DataFrame
│   ├── db.py              # F3：建表、UPSERT、查詢
│   └── pipeline.py        # 串接 fetch → parse → save（CLI 入口）
├── app.py                 # F5/F6：Streamlit 主程式
└── tests/
    └── test_pipeline.py   # 基本測試
```

### 1.4 資料庫 Schema
```sql
CREATE TABLE IF NOT EXISTS TemperatureForecasts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    regionName  TEXT    NOT NULL,
    dataDate    TEXT    NOT NULL,   -- 'YYYY-MM-DD'
    mint        REAL,
    maxt        REAL,
    fetchedAt   TEXT    DEFAULT (datetime('now','localtime')),
    UNIQUE(regionName, dataDate)   -- 讓 INSERT OR REPLACE / UPSERT 不重複
);
```

---

## 2. 執行流程（Phase 0 → Phase 7）

### Phase 0 — 環境與 Repo 初始化
**AI 要做的事**
1. 確認目前資料夾已 `git clone https://github.com/Kuonaiwei1126/Forecast-with-CWA-API.git`（若是空 repo 則 `git init` + `git remote add origin ...`）。
2. 建立 `.venv`，並產生 `requirements.txt`：
   ```
   requests
   python-dotenv
   pandas
   streamlit
   folium
   streamlit-folium
   ```
3. 建立 `.gitignore`（至少含 `.venv/`、`.env`、`__pycache__/`、`data/data.db`、`data/raw_forecast.json`、`.streamlit/secrets.toml`）。
4. 建立 `.env.example`；**確認 `.env` 已存在於本機且含 `CWA_API_KEY`**（由我手動建立，AI 不要印出其內容）。
5. 建立 `README.md` 骨架（專案簡介、安裝、執行方式、截圖區塊）。

**驗收**：`pip install -r requirements.txt` 成功；`git status` 不顯示 `.env`。
**Commit**：`Phase 0: project scaffold, gitignore, requirements`

---

### Phase 1 — 取得 CWA API 資料（F1）
**AI 要做的事**
1. `src/config.py`：
   - 用 `load_dotenv()` 讀 `CWA_API_KEY`，若為空則 raise 清楚的錯誤訊息。
   - 常數：`BASE_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/"`、`DATASET_ID = "F-D0047-091"`。
2. `src/fetch_cwa.py`：
   - `fetch_forecast(dataset_id=DATASET_ID, element_names=("MinT","MaxT")) -> dict`
   - 使用 `requests.get(url, params={"Authorization": key, "elementName": ..., "format": "JSON"}, timeout=15)`
   - 檢查 `resp.status_code == 200` 與 `data["success"] == "true"`；失敗要 raise 並印出 status 與前 300 字回應。
   - 成功後存到 `data/raw_forecast.json`（`ensure_ascii=False, indent=2`）。
3. 先實際呼叫一次，把回傳 JSON 的**最外層結構**（key 名稱、`locations` 的層次）貼給我看，確認欄位後再進 Phase 2。

**驗收**：`python -m src.fetch_cwa` 可成功下載並產生 `data/raw_forecast.json`。
**Commit**：`Phase 1: fetch CWA weekly forecast via Open Data API`

---

### Phase 2 — JSON 解析（F2）
**AI 要做的事**
1. `src/parse_forecast.py`：
   - `parse_forecast(raw: dict) -> pd.DataFrame`，欄位：`regionName, dataDate, mint, maxt`。
   - 遍歷 `records.locations[].location[]`，對每個 location 找 `weatherElement` 中 `elementName in ("MinT","MaxT")`；
   - 每個 element 的 `time[]` 內有 `startTime` 與數值（注意 CWA 新版格式可能是 `elementValue[0].value` 或 `elementValue[0].MinT`，**請以 raw json 實際內容為準**）。
   - 同一天可能有多個時段（白天/夜間）→ 以日期 groupby，`mint` 取 min、`maxt` 取 max。
   - `dataDate` 格式統一為 `YYYY-MM-DD`，數值轉 float。
2. 用 pandas 印出 `df.head(10)`、`df["regionName"].unique()`、`df["dataDate"].min()/max()` 給我確認。

**驗收**：DataFrame 無 NaN 的 regionName/dataDate；每個地區約 7 筆（一週）。
**Commit**：`Phase 2: parse MinT/MaxT into DataFrame`

---

### Phase 3 — SQLite 儲存與查詢驗證（F3、F4）
**AI 要做的事**
1. `src/db.py`：
   - `get_conn(db_path="data/data.db")`
   - `init_db(conn)`：執行 1.4 的 CREATE TABLE。
   - `upsert_forecasts(conn, df)`：`INSERT INTO ... ON CONFLICT(regionName, dataDate) DO UPDATE SET mint=excluded.mint, maxt=excluded.maxt, fetchedAt=...`。
   - `query_regions(conn) -> list[str]`、`query_by_region(conn, region) -> pd.DataFrame`（依 dataDate 排序）。
2. `src/pipeline.py`：CLI 入口，依序 fetch → parse → init_db → upsert，印出「寫入 N 筆」。
3. 驗證 SQL（請實際執行並貼結果）：
   ```sql
   SELECT COUNT(*) FROM TemperatureForecasts;
   SELECT DISTINCT regionName FROM TemperatureForecasts;
   SELECT * FROM TemperatureForecasts WHERE regionName = '臺中市' ORDER BY dataDate;
   ```
4. **連續執行兩次 `python -m src.pipeline`**，確認筆數不變（證明不重複插入）。

**驗收**：筆數穩定；查詢結果正確。
**Commit**：`Phase 3: SQLite storage with upsert and query helpers`

---

### Phase 4 — Streamlit Web App（F5）
**AI 要做的事**
1. `app.py`：
   - `st.set_page_config(page_title="Taiwan Weather Forecast", layout="wide")`
   - 標題：Taiwan Weather Forecast（HW1 — 人工智慧與資訊安全）
   - Sidebar：`st.selectbox("Select Region", regions)`、按鈕「重新抓取資料」（呼叫 pipeline 並 `st.cache_data.clear()`）。
   - 主區：`st.line_chart` 或 `plotly` 折線圖（MaxT 紅、MinT 藍，x 軸日期）；下方 `st.dataframe` 顯示 Date / MinT / MaxT。
   - 讀資料用 `@st.cache_data(ttl=3600)`。
2. 若 `data/data.db` 不存在，自動先跑一次 pipeline 並顯示提示。

**驗收**：`streamlit run app.py` 在 http://localhost:8501 正常顯示，切換地區圖表會更新。
**Commit**：`Phase 4: Streamlit dashboard with region selector and chart`

---

### Phase 5 — 台灣地圖視覺化（F6，進階）
**AI 要做的事**
1. 在 `src/config.py` 加入各縣市（或地區）經緯度字典 `REGION_COORDS`。
2. `app.py` 新增「地圖」分頁（`st.tabs(["折線圖", "地圖"])`）：
   - `st.selectbox("Select Date", dates)`
   - Folium 地圖中心 `[23.7, 121.0]`, zoom 7；每個地區一個 `CircleMarker`，顏色依 (mint+maxt)/2 分級：<20 藍、20–25 綠、25–30 黃、>30 紅；popup 顯示地區、Min、Max。
   - 用 `streamlit_folium.st_folium` 嵌入，附圖例。

**驗收**：切換日期地圖標記顏色會變化。
**Commit**：`Phase 5: Folium Taiwan map by date`

---

### Phase 6 — 程式品質、測試、安全檢查（對應資安課程重點）
**AI 要做的事**
1. `tests/test_pipeline.py`：
   - 測試 `parse_forecast` 以一份精簡的 sample json 能正確產出 DataFrame。
   - 測試 `upsert_forecasts` 執行兩次筆數不變（用 `:memory:` SQLite）。
2. 安全檢查清單（請逐項確認並回報）：
   - [ ] `git log -p | grep -i "CWA-"` 無任何 API Key 出現在歷史紀錄
   - [ ] `.env` 在 `.gitignore`，`.env.example` 不含真實 key
   - [ ] 所有外部輸入（API 回應）都有型別檢查與例外處理
   - [ ] SQL 全部使用參數化查詢（`?` placeholder），無字串拼接
   - [ ] `requests` 有設定 `timeout`，並驗證 HTTPS
3. 補齊 README.md：功能、架構圖（可用 Mermaid）、安裝與執行步驟、截圖、AI Agent 開發流程說明（本 pipeline 的使用方式）、資安考量一節。

**驗收**：`pytest` 全綠；README 完整。
**Commit**：`Phase 6: tests, security checklist, README`

---

### Phase 7 — 完成與交付
1. 最終 `git push origin main`，確認 GitHub 上的檔案樹與 1.3 一致。
2. 產出一段「作業摘要」（200 字內，繁體中文）：使用了哪些資料集、AI Agent 如何協助、遇到的問題與解法，供我貼進作業繳交表單。
3. （選配）說明如何部署到 Streamlit Community Cloud，並把 `CWA_API_KEY` 放在 Streamlit Secrets 而非程式碼。

---

## 3. 啟動指令（我在 VS Code 對 Claude 的第一句話）

```
請先閱讀 pipeline.md。我們要依照裡面的 Phase 0 → Phase 7 完成 HW1。
請先告訴我你對 Phase 0 的執行計畫（要建立哪些檔案、內容大綱），
我確認後再開始動手。全程使用繁體中文回覆，技術名詞保留英文。
```

---

## 4. 附錄：常用指令
```bash
# 環境
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 資料管線
python -m src.pipeline

# 網頁
streamlit run app.py

# 測試
pytest -q

# 版本管理
git status
git add .
git commit -m "Phase N: ..."
git push origin main
```
