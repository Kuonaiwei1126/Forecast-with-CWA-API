"""F3 / F4：SQLite 建表、UPSERT 與查詢工具。所有 SQL 皆使用參數化查詢。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from src.config import DB_PATH

TABLE_NAME = "TemperatureForecasts"

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    regionName  TEXT    NOT NULL,
    dataDate    TEXT    NOT NULL,   -- 'YYYY-MM-DD'
    mint        REAL,
    maxt        REAL,
    fetchedAt   TEXT    DEFAULT (datetime('now','localtime')),
    UNIQUE(regionName, dataDate)   -- 讓 UPSERT 不重複插入
);
"""

UPSERT_SQL = f"""
INSERT INTO {TABLE_NAME} (regionName, dataDate, mint, maxt, fetchedAt)
VALUES (?, ?, ?, ?, datetime('now','localtime'))
ON CONFLICT(regionName, dataDate) DO UPDATE SET
    mint      = excluded.mint,
    maxt      = excluded.maxt,
    fetchedAt = excluded.fetchedAt;
"""


def get_conn(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    """建立 SQLite 連線；傳入 ":memory:" 可用於測試。會自動建立 data/ 目錄。"""
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(db_path))


def init_db(conn: sqlite3.Connection) -> None:
    """建立資料表（若不存在）。"""
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()


def _nan_to_none(value):
    """pandas 的 NaN 無法直接寫入 SQLite 為 NULL，先轉成 None。"""
    if value is None or pd.isna(value):
        return None
    return float(value)


def upsert_forecasts(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """以 UPSERT 寫入 DataFrame，回傳處理的筆數（含新增與更新）。"""
    required = {"regionName", "dataDate", "mint", "maxt"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame 缺少欄位：{sorted(missing)}")

    rows = [
        (str(r.regionName), str(r.dataDate), _nan_to_none(r.mint), _nan_to_none(r.maxt))
        for r in df.itertuples(index=False)
    ]
    conn.executemany(UPSERT_SQL, rows)
    conn.commit()
    return len(rows)


def count_rows(conn: sqlite3.Connection) -> int:
    """回傳資料表總筆數。"""
    return conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]


def query_regions(conn: sqlite3.Connection) -> list[str]:
    """回傳所有地區名稱（依名稱排序）。"""
    cur = conn.execute(
        f"SELECT DISTINCT regionName FROM {TABLE_NAME} ORDER BY regionName"
    )
    return [row[0] for row in cur.fetchall()]


def query_dates(conn: sqlite3.Connection) -> list[str]:
    """回傳所有日期（升冪）。"""
    cur = conn.execute(
        f"SELECT DISTINCT dataDate FROM {TABLE_NAME} ORDER BY dataDate"
    )
    return [row[0] for row in cur.fetchall()]


def query_by_region(conn: sqlite3.Connection, region: str) -> pd.DataFrame:
    """回傳指定地區的一週預報，依日期排序。使用 ? placeholder 防止 SQL injection。"""
    return pd.read_sql_query(
        f"SELECT regionName, dataDate, mint, maxt, fetchedAt "
        f"FROM {TABLE_NAME} WHERE regionName = ? ORDER BY dataDate",
        conn,
        params=(region,),
    )


def query_by_date(conn: sqlite3.Connection, date: str) -> pd.DataFrame:
    """回傳指定日期所有地區的預報（供地圖使用）。"""
    return pd.read_sql_query(
        f"SELECT regionName, dataDate, mint, maxt "
        f"FROM {TABLE_NAME} WHERE dataDate = ? ORDER BY regionName",
        conn,
        params=(date,),
    )


def query_all(conn: sqlite3.Connection) -> pd.DataFrame:
    """回傳全部資料。"""
    return pd.read_sql_query(
        f"SELECT regionName, dataDate, mint, maxt, fetchedAt "
        f"FROM {TABLE_NAME} ORDER BY regionName, dataDate",
        conn,
    )
