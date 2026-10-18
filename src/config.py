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
