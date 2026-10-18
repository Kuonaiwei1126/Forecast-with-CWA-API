"""專案設定：讀取 .env 中的 API Key，並定義常數。"""
import os
from pathlib import Path

from dotenv import load_dotenv

# 專案根目錄（src 的上一層）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_JSON_PATH = DATA_DIR / "raw_forecast.json"
DB_PATH = DATA_DIR / "data.db"

# CWA Open Data API
BASE_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/"
DATASET_ID = "F-D0047-091"          # 臺灣各縣市一週天氣預報
FALLBACK_DATASET_ID = "F-C0032-001"  # 36 小時天氣預報（備援）
REQUEST_TIMEOUT = 15                 # 秒

# 要向 API 索取的天氣要素（新版 API 以中文命名）
ELEMENT_MIN_T = "最低溫度"
ELEMENT_MAX_T = "最高溫度"
DEFAULT_ELEMENTS = (ELEMENT_MIN_T, ELEMENT_MAX_T)

# ElementValue 內對應的欄位名稱（實測 F-D0047-091 回應）
VALUE_KEY_MIN_T = "MinTemperature"
VALUE_KEY_MAX_T = "MaxTemperature"

# 載入 .env（若檔案不存在不會報錯，只是讀不到變數）
load_dotenv(PROJECT_ROOT / ".env")


def get_api_key() -> str:
    """回傳 CWA_API_KEY，若未設定則丟出清楚的錯誤訊息。"""
    key = os.getenv("CWA_API_KEY", "").strip()
    if not key or key == "your_cwa_api_key_here":
        raise RuntimeError(
            "找不到 CWA_API_KEY。請在專案根目錄建立 .env 檔並加入："
            "CWA_API_KEY=<你的金鑰>（可參考 .env.example）。"
        )
    return key


# ---------------------------------------------------------------------------
# 各縣市經緯度（取自 CWA F-D0047-091 回應中的 Latitude / Longitude 欄位）
# 供 Folium 地圖標記使用
# ---------------------------------------------------------------------------
REGION_COORDS: dict[str, tuple[float, float]] = {
    "基隆市": (25.153191, 121.759355),
    "臺北市": (25.035095, 121.558742),
    "新北市": (25.011540, 121.450888),
    "桃園市": (24.995720, 121.293452),
    "新竹市": (24.818109, 120.962110),
    "新竹縣": (24.841245, 120.995698),
    "苗栗縣": (24.563327, 120.810970),
    "臺中市": (24.142918, 120.662950),
    "彰化縣": (24.082575, 120.534059),
    "南投縣": (23.913301, 120.679244),
    "雲林縣": (23.698834, 120.518874),
    "嘉義市": (23.480384, 120.445361),
    "嘉義縣": (23.460227, 120.323988),
    "臺南市": (22.996394, 120.160419),
    "高雄市": (22.623511, 120.304085),
    "屏東縣": (22.664236, 120.483389),
    "宜蘭縣": (24.753707, 121.745083),
    "花蓮縣": (23.983897, 121.598641),
    "臺東縣": (22.756487, 121.138672),
    "澎湖縣": (23.567554, 119.570666),
    "金門縣": (24.434365, 118.312425),
    "連江縣": (26.154204, 119.929303),
}

# 地圖預設中心與縮放
MAP_CENTER = (23.7, 121.0)
MAP_ZOOM = 7

# 平均氣溫顏色分級：(上限（不含）, 顏色, 圖例文字)
TEMP_COLOR_BINS = [
    (20.0, "#1f77b4", "< 20 °C"),
    (25.0, "#2ca02c", "20 – 25 °C"),
    (30.0, "#ffbf00", "25 – 30 °C"),
    (float("inf"), "#d62728", "> 30 °C"),
]
