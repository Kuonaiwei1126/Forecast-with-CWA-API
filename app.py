"""F5 / F6：Streamlit 互動式網頁 — Taiwan Weather Forecast（折線圖 + Folium 台灣地圖）。

執行：streamlit run app.py
"""
from __future__ import annotations

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from src.config import DB_PATH, MAP_CENTER, MAP_ZOOM, REGION_COORDS, TEMP_COLOR_BINS
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
# 地圖
# ---------------------------------------------------------------------------
def temp_to_color(avg_temp: float) -> str:
    """依平均氣溫回傳分級顏色：<20 藍、20–25 綠、25–30 黃、>30 紅。"""
    for upper, color, _ in TEMP_COLOR_BINS:
        if avg_temp < upper:
            return color
    return TEMP_COLOR_BINS[-1][1]


def build_map(day_df: pd.DataFrame, date: str) -> folium.Map:
    """建立 Folium 地圖：每個地區一個 CircleMarker，顏色依 (mint+maxt)/2 分級。"""
    fmap = folium.Map(location=list(MAP_CENTER), zoom_start=MAP_ZOOM, tiles="OpenStreetMap")

    missing: list[str] = []
    for row in day_df.itertuples(index=False):
        coords = REGION_COORDS.get(row.regionName)
        if coords is None:
            missing.append(row.regionName)
            continue
        if pd.isna(row.mint) or pd.isna(row.maxt):
            continue
        avg = (row.mint + row.maxt) / 2
        color = temp_to_color(avg)
        popup_html = (
            f"<b>{row.regionName}</b><br>{date}<br>"
            f"Min: {row.mint:.0f} °C<br>Max: {row.maxt:.0f} °C<br>Avg: {avg:.1f} °C"
        )
        folium.CircleMarker(
            location=list(coords),
            radius=11,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.85,
            weight=2,
            popup=folium.Popup(popup_html, max_width=200),
            tooltip=f"{row.regionName}  {row.mint:.0f}–{row.maxt:.0f} °C",
        ).add_to(fmap)

    if missing:
        st.caption(f"以下地區無座標資料，未顯示於地圖：{', '.join(missing)}")

    # 圖例（固定在右下角的 HTML）
    legend_items = "".join(
        f'<div><span style="display:inline-block;width:12px;height:12px;'
        f'border-radius:50%;background:{color};margin-right:6px;"></span>{label}</div>'
        for _, color, label in TEMP_COLOR_BINS
    )
    legend_html = (
        '<div style="position:fixed;bottom:30px;right:30px;z-index:9999;'
        'background:white;padding:10px 12px;border:1px solid #999;border-radius:6px;'
        'font-size:13px;line-height:1.6;box-shadow:0 1px 4px rgba(0,0,0,.3);">'
        '<b>平均氣溫 (MinT+MaxT)/2</b>' + legend_items + "</div>"
    )
    fmap.get_root().html.add_child(folium.Element(legend_html))
    return fmap


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

    tab_chart, tab_map = st.tabs(["折線圖", "地圖"])

    with tab_chart:
        # 折線圖
        st.plotly_chart(build_line_chart(region_df, region), width="stretch")

        # 表格
        table = region_df.rename(
            columns={"dataDate": "Date", "mint": "MinT (°C)", "maxt": "MaxT (°C)"}
        )[["Date", "MinT (°C)", "MaxT (°C)"]]
        st.dataframe(table, width="stretch", hide_index=True)

    with tab_map:
        dates = sorted(all_df["dataDate"].unique())
        date = st.selectbox("Select Date", dates, index=0)
        day_df = all_df[all_df["dataDate"] == date]

        m1, m2, m3 = st.columns(3)
        hottest = day_df.loc[day_df["maxt"].idxmax()]
        coldest = day_df.loc[day_df["mint"].idxmin()]
        m1.metric("日期", date)
        m2.metric("最熱地區", f"{hottest['regionName']} {hottest['maxt']:.0f} °C")
        m3.metric("最冷地區", f"{coldest['regionName']} {coldest['mint']:.0f} °C")

        st_folium(build_map(day_df, date), width=None, height=600, returned_objects=[])


if __name__ == "__main__":
    main()
