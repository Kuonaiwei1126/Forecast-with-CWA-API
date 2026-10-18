"""F5：Streamlit 互動式網頁 — Taiwan Weather Forecast。

執行：streamlit run app.py
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.config import DB_PATH
from src.db import get_conn, init_db, query_all, query_regions
from src.pipeline import run_pipeline

st.set_page_config(page_title="Taiwan Weather Forecast", layout="wide")


# ---------------------------------------------------------------------------
# 資料存取
# ---------------------------------------------------------------------------
def ensure_database() -> None:
    """若 data/data.db 不存在，先跑一次管線建立資料。"""
    if DB_PATH.exists():
        return
    with st.spinner("找不到資料庫，正在從 CWA 下載一週預報..."):
        try:
            stats = run_pipeline(verbose=False)
        except Exception as exc:
            st.error(f"初始化資料失敗：{exc}")
            st.stop()
    st.info(f"已建立資料庫並寫入 {stats['written']} 筆資料。")


@st.cache_data(ttl=3600)
def load_all() -> pd.DataFrame:
    """從 SQLite 讀取全部預報資料（快取 1 小時）。"""
    conn = get_conn()
    try:
        init_db(conn)
        return query_all(conn)
    finally:
        conn.close()


@st.cache_data(ttl=3600)
def load_regions() -> list[str]:
    conn = get_conn()
    try:
        init_db(conn)
        return query_regions(conn)
    finally:
        conn.close()


def refresh_data() -> None:
    """重新抓取 CWA 資料並清除快取。"""
    try:
        stats = run_pipeline(verbose=False)
    except Exception as exc:
        st.sidebar.error(f"重新抓取失敗：{exc}")
        return
    st.cache_data.clear()
    st.sidebar.success(
        f"已更新：{stats['regions']} 個地區，{stats['date_min']} ~ {stats['date_max']}，"
        f"寫入 {stats['written']} 筆（新增 {stats['new_rows']} 筆）"
    )


# ---------------------------------------------------------------------------
# 圖表
# ---------------------------------------------------------------------------
def build_line_chart(df: pd.DataFrame, region: str) -> go.Figure:
    """MaxT 紅線、MinT 藍線的一週氣溫折線圖。"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["dataDate"], y=df["maxt"], name="MaxT (°C)",
        mode="lines+markers+text", line=dict(color="#d62728", width=3),
        text=df["maxt"].map(lambda v: f"{v:.0f}"), textposition="top center",
    ))
    fig.add_trace(go.Scatter(
        x=df["dataDate"], y=df["mint"], name="MinT (°C)",
        mode="lines+markers+text", line=dict(color="#1f77b4", width=3),
        text=df["mint"].map(lambda v: f"{v:.0f}"), textposition="bottom center",
    ))
    fig.update_layout(
        title=f"{region} 一週氣溫預報",
        xaxis_title="日期", yaxis_title="溫度 (°C)",
        hovermode="x unified", legend=dict(orientation="h", y=1.1),
        margin=dict(l=40, r=20, t=60, b=40), height=450,
    )
    fig.update_xaxes(type="category")
    return fig


# ---------------------------------------------------------------------------
# 主程式
# ---------------------------------------------------------------------------
def main() -> None:
    st.title("Taiwan Weather Forecast")
    st.caption("HW1 — 人工智慧與資訊安全｜資料來源：中央氣象署開放資料平台（F-D0047-091）")

    ensure_database()

    regions = load_regions()
    if not regions:
        st.warning("資料庫中沒有資料，請按左側「重新抓取資料」。")

    # Sidebar
    st.sidebar.header("設定")
    region = st.sidebar.selectbox("Select Region", regions, index=0 if regions else None)
    if st.sidebar.button("重新抓取資料", width="stretch"):
        refresh_data()
        st.rerun()

    all_df = load_all()
    if all_df.empty or region is None:
        st.stop()

    fetched_at = all_df["fetchedAt"].max()
    st.sidebar.caption(f"資料更新時間：{fetched_at}")

    region_df = (
        all_df[all_df["regionName"] == region]
        .sort_values("dataDate")
        .reset_index(drop=True)
    )

    # 指標列
    c1, c2, c3 = st.columns(3)
    c1.metric("地區", region)
    c2.metric("一週最高溫", f"{region_df['maxt'].max():.0f} °C")
    c3.metric("一週最低溫", f"{region_df['mint'].min():.0f} °C")

    # 折線圖
    st.plotly_chart(build_line_chart(region_df, region), width="stretch")

    # 表格
    table = region_df.rename(
        columns={"dataDate": "Date", "mint": "MinT (°C)", "maxt": "MaxT (°C)"}
    )[["Date", "MinT (°C)", "MaxT (°C)"]]
    st.dataframe(table, width="stretch", hide_index=True)


if __name__ == "__main__":
    main()
