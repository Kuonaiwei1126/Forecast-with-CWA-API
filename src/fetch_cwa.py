"""F1：呼叫 CWA Open Data API 取得一週天氣預報，並將原始 JSON 存檔。"""
import json
from pathlib import Path
from typing import Iterable

import requests

from src.config import (
    BASE_URL,
    DATASET_ID,
    DEFAULT_ELEMENTS,
    RAW_JSON_PATH,
    REQUEST_TIMEOUT,
    get_api_key,
)


def fetch_forecast(
    dataset_id: str = DATASET_ID,
    element_names: Iterable[str] = DEFAULT_ELEMENTS,
    save_path: Path | None = RAW_JSON_PATH,
) -> dict:
    """呼叫 CWA API 取得指定資料集，回傳解析後的 dict。

    Args:
        dataset_id: CWA 資料集代碼，預設為一週縣市預報 F-D0047-091。
        element_names: 要取得的天氣要素（CWA 新版 API 使用中文名稱，
            例如 "最低溫度"、"最高溫度"），預設只取這兩項以縮小回應。
        save_path: 原始 JSON 存檔路徑；傳入 None 則不存檔。

    Raises:
        RuntimeError: HTTP 狀態非 200、回傳非 JSON、或 success 欄位不為 "true"。
    """
    url = f"{BASE_URL}{dataset_id}"
    params = {
        "Authorization": get_api_key(),
        "format": "JSON",
    }
    if element_names:
        # CWA 新版 API 的參數名為 ElementName（大寫 E），值為中文要素名稱、逗號分隔。
        # 實測：舊版 elementName=MinT,MaxT 會被忽略而回傳全部 15 個要素。
        params["ElementName"] = ",".join(element_names)

    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise RuntimeError(f"呼叫 CWA API 失敗（網路錯誤）：{exc}") from exc

    if resp.status_code != 200:
        raise RuntimeError(
            f"CWA API 回傳 HTTP {resp.status_code}：{resp.text[:300]}"
        )

    try:
        data = resp.json()
    except ValueError as exc:
        raise RuntimeError(
            f"CWA API 回傳非 JSON 內容：{resp.text[:300]}"
        ) from exc

    # CWA 的 success 欄位是字串 "true"，不是布林值
    if not isinstance(data, dict) or str(data.get("success", "")).lower() != "true":
        raise RuntimeError(
            f"CWA API 回傳 success != true：{json.dumps(data, ensure_ascii=False)[:300]}"
        )

    if save_path is not None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    return data


def describe_structure(obj, indent: int = 0, max_list_items: int = 1) -> str:
    """遞迴印出 JSON 的 key 結構（除錯用），list 只展開第一個元素。"""
    pad = "  " * indent
    lines = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{pad}{k}: {type(v).__name__}"
                             + (f"[{len(v)}]" if isinstance(v, list) else ""))
                lines.append(describe_structure(v, indent + 1, max_list_items))
            else:
                preview = str(v)
                if len(preview) > 40:
                    preview = preview[:40] + "..."
                lines.append(f"{pad}{k}: {type(v).__name__} = {preview!r}")
    elif isinstance(obj, list):
        for item in obj[:max_list_items]:
            lines.append(describe_structure(item, indent, max_list_items))
    return "\n".join(line for line in lines if line)


if __name__ == "__main__":
    # 直接執行：下載資料、存檔，並印出最外層結構供人工確認
    result = fetch_forecast()
    print(f"已儲存原始資料至 {RAW_JSON_PATH}")
    print("=== JSON 結構（list 僅展開第一個元素）===")
    print(describe_structure(result))
