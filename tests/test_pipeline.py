"""基本測試：JSON 解析與 SQLite UPSERT 行為。執行：pytest -q"""
import pandas as pd
import pytest

from src.db import count_rows, get_conn, init_db, query_by_region, query_regions, upsert_forecasts
from src.parse_forecast import parse_forecast


# ---------------------------------------------------------------------------
# 精簡版 CWA F-D0047-091 回應（2 個縣市、2 天、各含日/夜時段）
# ---------------------------------------------------------------------------
def _time(start: str, end: str, key: str, value: str) -> dict:
    return {"StartTime": start, "EndTime": end, "ElementValue": [{key: value}]}


SAMPLE_JSON = {
    "success": "true",
    "records": {
        "Locations": [
            {
                "LocationsName": "台灣",
                "Location": [
                    {
                        "LocationName": "臺中市",
                        "WeatherElement": [
                            {
                                "ElementName": "最低溫度",
                                "Time": [
                                    _time("2026-10-18T06:00:00+08:00", "2026-10-18T18:00:00+08:00", "MinTemperature", "24"),
                                    _time("2026-10-18T18:00:00+08:00", "2026-10-19T06:00:00+08:00", "MinTemperature", "22"),
                                    _time("2026-10-19T06:00:00+08:00", "2026-10-19T18:00:00+08:00", "MinTemperature", "23"),
                                ],
                            },
                            {
                                "ElementName": "最高溫度",
                                "Time": [
                                    _time("2026-10-18T06:00:00+08:00", "2026-10-18T18:00:00+08:00", "MaxTemperature", "33"),
                                    _time("2026-10-18T18:00:00+08:00", "2026-10-19T06:00:00+08:00", "MaxTemperature", "28"),
                                    _time("2026-10-19T06:00:00+08:00", "2026-10-19T18:00:00+08:00", "MaxTemperature", "31"),
                                ],
                            },
                        ],
                    },
                    {
                        "LocationName": "臺北市",
                        "WeatherElement": [
                            {
                                "ElementName": "最低溫度",
                                "Time": [_time("2026-10-18T06:00:00+08:00", "2026-10-18T18:00:00+08:00", "MinTemperature", "-")],
                            },
                            {
                                "ElementName": "最高溫度",
                                "Time": [_time("2026-10-18T06:00:00+08:00", "2026-10-18T18:00:00+08:00", "MaxTemperature", "30")],
                            },
                        ],
                    },
                ],
            }
        ]
    },
}


# ---------------------------------------------------------------------------
# parse_forecast
# ---------------------------------------------------------------------------
def test_parse_forecast_columns_and_shape():
    df = parse_forecast(SAMPLE_JSON)
    assert list(df.columns) == ["regionName", "dataDate", "mint", "maxt"]
    # 臺中市 2 天 + 臺北市 1 天
    assert len(df) == 3
    assert set(df["regionName"]) == {"臺中市", "臺北市"}


def test_parse_forecast_aggregates_day_and_night():
    """同一天日/夜兩個時段：mint 取 min、maxt 取 max。"""
    df = parse_forecast(SAMPLE_JSON).set_index(["regionName", "dataDate"])
    assert df.loc[("臺中市", "2026-10-18"), "mint"] == 22.0
    assert df.loc[("臺中市", "2026-10-18"), "maxt"] == 33.0
    assert df.loc[("臺中市", "2026-10-19"), "mint"] == 23.0
    assert df.loc[("臺中市", "2026-10-19"), "maxt"] == 31.0


def test_parse_forecast_handles_invalid_value_as_nan():
    """API 回傳 "-" 之類無法轉換的數值應變成 NaN，而不是讓整個解析失敗。"""
    df = parse_forecast(SAMPLE_JSON).set_index(["regionName", "dataDate"])
    assert pd.isna(df.loc[("臺北市", "2026-10-18"), "mint"])
    assert df.loc[("臺北市", "2026-10-18"), "maxt"] == 30.0


def test_parse_forecast_rejects_bad_input():
    with pytest.raises(TypeError):
        parse_forecast("not a dict")
    with pytest.raises(ValueError):
        parse_forecast({"records": {"Locations": []}})


# ---------------------------------------------------------------------------
# upsert_forecasts（使用 in-memory SQLite）
# ---------------------------------------------------------------------------
@pytest.fixture
def mem_conn():
    conn = get_conn(":memory:")
    init_db(conn)
    yield conn
    conn.close()


def test_upsert_twice_does_not_duplicate(mem_conn):
    df = parse_forecast(SAMPLE_JSON)
    upsert_forecasts(mem_conn, df)
    first = count_rows(mem_conn)
    upsert_forecasts(mem_conn, df)
    second = count_rows(mem_conn)
    assert first == len(df) == 3
    assert second == first


def test_upsert_updates_existing_values(mem_conn):
    df = parse_forecast(SAMPLE_JSON)
    upsert_forecasts(mem_conn, df)
    # 模擬 CWA 更新預報：臺中市 10/18 最高溫從 33 變 35
    updated = df.copy()
    updated.loc[(updated.regionName == "臺中市") & (updated.dataDate == "2026-10-18"), "maxt"] = 35.0
    upsert_forecasts(mem_conn, updated)
    result = query_by_region(mem_conn, "臺中市")
    assert count_rows(mem_conn) == 3
    assert result.loc[result.dataDate == "2026-10-18", "maxt"].iloc[0] == 35.0


def test_query_helpers(mem_conn):
    upsert_forecasts(mem_conn, parse_forecast(SAMPLE_JSON))
    assert query_regions(mem_conn) == ["臺中市", "臺北市"]
    taichung = query_by_region(mem_conn, "臺中市")
    assert list(taichung["dataDate"]) == ["2026-10-18", "2026-10-19"]


def test_query_by_region_is_safe_against_injection(mem_conn):
    """參數化查詢：注入字串不會被當成 SQL 執行，只會查不到資料。"""
    upsert_forecasts(mem_conn, parse_forecast(SAMPLE_JSON))
    result = query_by_region(mem_conn, "' OR 1=1 --")
    assert result.empty
    assert count_rows(mem_conn) == 3
