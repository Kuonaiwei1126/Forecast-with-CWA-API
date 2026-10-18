"""資料管線 CLI 入口：fetch → parse → init_db → upsert。

用法：
    python -m src.pipeline
"""
from __future__ import annotations

import sys
from pathlib import Path

from src.config import DB_PATH
from src.db import count_rows, get_conn, init_db, upsert_forecasts
from src.fetch_cwa import fetch_forecast
from src.parse_forecast import parse_forecast


def run_pipeline(db_path: str | Path = DB_PATH, verbose: bool = True) -> dict:
    """執行完整管線，回傳統計資訊 dict（供 CLI 與 Streamlit 共用）。"""
    raw = fetch_forecast()
    df = parse_forecast(raw)

    conn = get_conn(db_path)
    try:
        init_db(conn)
        before = count_rows(conn)
        written = upsert_forecasts(conn, df)
        after = count_rows(conn)
    finally:
        conn.close()

    stats = {
        "regions": int(df["regionName"].nunique()),
        "date_min": str(df["dataDate"].min()),
        "date_max": str(df["dataDate"].max()),
        "written": written,
        "rows_before": before,
        "rows_after": after,
        "new_rows": after - before,
    }
    if verbose:
        print(f"地區數 {stats['regions']}，日期 {stats['date_min']} ~ {stats['date_max']}")
        print(f"寫入 {written} 筆（UPSERT）；資料表筆數 {before} -> {after}（新增 {stats['new_rows']} 筆）")
    return stats


if __name__ == "__main__":
    try:
        run_pipeline()
    except Exception as exc:  # 讓 CLI 使用者看到清楚的錯誤而非 traceback
        print(f"[錯誤] 管線執行失敗：{exc}", file=sys.stderr)
        sys.exit(1)
