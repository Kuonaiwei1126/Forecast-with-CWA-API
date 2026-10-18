# Taiwan Weather Forecast — Forecast with CWA API

> 課程：人工智慧與資訊安全（NCHU）｜Homework 1
> 作者：郭乃瑋 Leo Kuo

利用 AI Agent（VS Code + Claude）以自然語言驅動開發：從中央氣象署（CWA）開放資料平台取得一週氣溫預報，
存入 SQLite，並以 Streamlit 建立互動式網頁與台灣地圖視覺化。

## 功能

- 取得 CWA 一週天氣預報（資料集 F-D0047-091），抽出各縣市每日最低溫 / 最高溫
- 以 SQLite 儲存，重複執行不重複插入（UPSERT）
- Streamlit 網頁：選擇縣市顯示一週氣溫折線圖與表格
- Folium 台灣地圖：依日期顯示各縣市平均氣溫，顏色分級

## 安裝

```bash
git clone https://github.com/Kuonaiwei1126/Forecast-with-CWA-API.git
cd Forecast-with-CWA-API
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # 然後把 CWA_API_KEY 換成你的金鑰
```

CWA API Key 請至 https://opendata.cwa.gov.tw/ 註冊後於「API 授權碼」頁面取得。

## 執行

```bash
python -m src.pipeline   # 抓取 → 解析 → 存入 data/data.db
streamlit run app.py     # 開啟 http://localhost:8501
pytest -q                # 執行測試
```

## 截圖

（待補）

## 專案結構

（待補）
