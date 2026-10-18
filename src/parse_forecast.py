"""F2：把 CWA F-D0047-091 的 JSON 解析成 DataFrame（regionName, dataDate, mint, maxt）。

實測的 JSON 結構（2026-10 新版 API，key 為大寫開頭）：
    records.Locations[0].Location[]            # 22 個縣市
        .LocationName                          # 例如 "臺中市"
        .WeatherElement[]
            .ElementName                       # "最低溫度" / "最高溫度"
            .Time[]                            # 7 天 × 日/夜 = 14 個時段
                .StartTime / .EndTime          # ISO 8601，含 +08:00
                .ElementValue[0].MinTemperature 或 .MaxTemperature（字串）
"""
from __future__ import annotations

import json
from typing import Any

import pandas as pd

from src.config import RAW_JSON_PATH, VALUE_KEY_MAX_T, VALUE_KEY_MIN_T

COLUMNS = ["regionName", "dataDate", "mint", "maxt"]


def _to_float(value: Any) -> float | None:
    """把 API 的字串數值轉成 float；無法轉換（如 "-"、空字串）則回傳 None。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_date(time_entry: dict) -> str | None:
    """從 Time 項目取出日期（YYYY-MM-DD）。優先用 StartTime，其次 DataTime。"""
    raw = time_entry.get("StartTime") or time_entry.get("DataTime")
    if not isinstance(raw, str) or len(raw) < 10:
        return None
    # ISO 字串前 10 碼即為日期；時區固定 +08:00，不需轉換
    return raw[:10]


def _iter_locations(raw: dict):
    """逐一產出 Location dict，同時容忍新舊兩種大小寫的 key。"""
    records = raw.get("records", {})
    locations_groups = records.get("Locations") or records.get("locations") or []
    for group in locations_groups:
        if not isinstance(group, dict):
            continue
        for loc in group.get("Location") or group.get("location") or []:
            if isinstance(loc, dict):
                yield loc


def _extract_records(raw: dict) -> list[dict]:
    """展開所有 (地區, 時段) 的溫度值，尚未依日期彙整。"""
    rows: list[dict] = []
    for loc in _iter_locations(raw):
        region = loc.get("LocationName") or loc.get("locationName")
        if not region:
            continue
        elements = loc.get("WeatherElement") or loc.get("weatherElement") or []
        for element in elements:
            if not isinstance(element, dict):
                continue
            for t in element.get("Time") or element.get("time") or []:
                if not isinstance(t, dict):
                    continue
                date = _extract_date(t)
                if date is None:
                    continue
                values = t.get("ElementValue") or t.get("elementValue") or []
                if not values or not isinstance(values[0], dict):
                    continue
                ev = values[0]
                # 依 ElementValue 內的 key 判斷是最低溫還是最高溫，比 ElementName 更穩定
                if VALUE_KEY_MIN_T in ev:
                    rows.append({"regionName": region, "dataDate": date,
                                 "mint": _to_float(ev[VALUE_KEY_MIN_T]), "maxt": None})
                elif VALUE_KEY_MAX_T in ev:
                    rows.append({"regionName": region, "dataDate": date,
                                 "mint": None, "maxt": _to_float(ev[VALUE_KEY_MAX_T])})
    return rows


def parse_forecast(raw: dict) -> pd.DataFrame:
    """把 CWA 原始 JSON 轉成每地區每日一筆的 DataFrame。

    同一天有日/夜兩個時段：mint 取當日最小值、maxt 取當日最大值。

    Returns:
        欄位為 regionName (str), dataDate (str 'YYYY-MM-DD'), mint (float), maxt (float)，
        依 regionName、dataDate 排序。
    """
    if not isinstance(raw, dict):
        raise TypeError("raw 必須是 dict（CWA API 的 JSON 回應）")

    rows = _extract_records(raw)
    if not rows:
        raise ValueError("JSON 中找不到任何溫度資料，請檢查資料集代碼或 API 回應格式")

    df = pd.DataFrame(rows, columns=COLUMNS)
    df = (
        df.groupby(["regionName", "dataDate"], as_index=False)
        .agg(mint=("mint", "min"), maxt=("maxt", "max"))
        .sort_values(["regionName", "dataDate"])
        .reset_index(drop=True)
    )
    return df[COLUMNS]


def load_raw_json(path=RAW_JSON_PATH) -> dict:
    """讀取先前存檔的原始 JSON。"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    # 直接執行：讀取 data/raw_forecast.json，印出摘要供人工確認
    df = parse_forecast(load_raw_json())
    pd.set_option("display.width", 120)
    print(df.head(10))
    print("\n地區數:", df["regionName"].nunique(), "| 地區清單:", list(df["regionName"].unique()))
    print("日期範圍:", df["dataDate"].min(), "~", df["dataDate"].max())
    print("總筆數:", len(df), "| 每地區筆數:", df.groupby("regionName").size().unique())
    print("NaN 檢查 -> regionName:", df["regionName"].isna().sum(),
          "dataDate:", df["dataDate"].isna().sum(),
          "mint:", df["mint"].isna().sum(), "maxt:", df["maxt"].isna().sum())
