import datetime as dt
from typing import Dict, List

import pandas as pd
import plotly.express as px
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="Global Top 10 Market Cap Stock Dashboard",
    page_icon="📈",
    layout="wide",
)

DEFAULT_COMPANIES: Dict[str, str] = {
    "NVIDIA": "NVDA",
    "Apple": "AAPL",
    "Alphabet": "GOOGL",
    "Microsoft": "MSFT",
    "Amazon": "AMZN",
    "TSMC": "TSM",
    "Broadcom": "AVGO",
    "Tesla": "TSLA",
    "Meta Platforms": "META",
    "Eli Lilly": "LLY",
}

st.title("📈 글로벌 시가총액 TOP10 최근 1년 주가 대시보드")
st.caption(
    "Yahoo Finance(yfinance) 데이터를 사용합니다. 시가총액 순위는 앱 코드의 기본값이며, "
    "시점에 따라 바뀔 수 있습니다. 인간들이 시장을 매일 흔들어대니까요."
)

with st.sidebar:
    st.header("설정")
    selected_names: List[str] = st.multiselect(
        "표시할 기업",
        options=list(DEFAULT_COMPANIES.keys()),
        default=list(DEFAULT_COMPANIES.keys()),
    )
    period = st.selectbox("기간", ["1y", "6mo", "3mo", "5y"], index=0)
    normalize = st.toggle("시작일 기준 수익률(%)로 보기", value=True)
    show_volume = st.toggle("거래량 차트 표시", value=False)

selected_tickers = [DEFAULT_COMPANIES[name] for name in selected_names]

@st.cache_data(ttl=60 * 30, show_spinner=False)
def load_prices(tickers: List[str], period: str) -> pd.DataFrame:
    if not tickers:
        return pd.DataFrame()

    raw = yf.download(
        tickers=tickers,
        period=period,
        interval="1d",
        auto_adjust=True,
        group_by="column",
        progress=False,
        threads=True,
    )

    if raw.empty:
        return pd.DataFrame()

    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"].copy()
    else:
        close = raw[["Close"]].copy()
        close.columns = tickers

    close = close.dropna(how="all")
    close.index = pd.to_datetime(close.index)
    return close

@st.cache_data(ttl=60 * 30, show_spinner=False)
def load_volume(tickers: List[str], period: str) -> pd.DataFrame:
    raw = yf.download(
        tickers=tickers,
        period=period,
        interval="1d",
        auto_adjust=True,
        group_by="column",
        progress=False,
        threads=True,
    )
    if raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        volume = raw["Volume"].copy()
    else:
        volume = raw[["Volume"]].copy()
        volume.columns = tickers
    volume.index = pd.to_datetime(volume.index)
    return volume.dropna(how="all")

@st.cache_data(ttl=60 * 30, show_spinner=False)
def load_snapshot(tickers: List[str]) -> pd.DataFrame:
    rows = []
    for company, ticker in DEFAULT_COMPANIES.items():
        if ticker not in tickers:
            continue
        info = yf.Ticker(ticker).fast_info
        rows.append(
            {
                "기업": company,
                "티커": ticker,
                "현재가": info.get("last_price"),
                "시가총액": info.get("market_cap"),
                "통화": info.get("currency"),
            }
        )
    return pd.DataFrame(rows)

if not selected_tickers:
    st.warning("왼쪽에서 최소 1개 기업을 선택하세요. 텅 빈 차트는 현대미술이지 대시보드가 아닙니다.")
    st.stop()

with st.spinner("Yahoo Finance에서 데이터를 가져오는 중입니다..."):
    prices = load_prices(selected_tickers, period)
    snapshot = load_snapshot(selected_tickers)

if prices.empty:
    st.error("데이터를 가져오지 못했습니다. 네트워크, 티커, 또는 Yahoo Finance 응답 상태를 확인하세요.")
    st.stop()

company_by_ticker = {ticker: company for company, ticker in DEFAULT_COMPANIES.items()}
prices = prices.rename(columns=company_by_ticker)

latest_date = prices.index.max().strftime("%Y-%m-%d")
first_valid = prices.apply(lambda s: s.dropna().iloc[0] if not s.dropna().empty else None)
last_valid = prices.apply(lambda s: s.dropna().iloc[-1] if not s.dropna().empty else None)
returns = ((last_valid / first_valid) - 1) * 100

col1, col2, col3 = st.columns(3)
col1.metric("선택 기업 수", f"{len(selected_tickers)}개")
col2.metric("최신 거래일", latest_date)
col3.metric("최고 수익률", f"{returns.max():.2f}%")

st.subheader("최근 주가 변화")
if normalize:
    chart_df = ((prices / prices.apply(lambda s: s.dropna().iloc[0])) - 1) * 100
    y_label = "수익률(%)"
    title = "시작일 기준 누적 수익률"
else:
    chart_df = prices
    y_label = "조정 종가"
    title = "조정 종가 추이"

long_df = chart_df.reset_index().melt(id_vars="Date", var_name="기업", value_name=y_label)
fig = px.line(
    long_df,
    x="Date",
    y=y_label,
    color="기업",
    title=title,
    hover_data={"Date": "|%Y-%m-%d"},
)
fig.update_layout(
    hovermode="x unified",
    legend_title_text="기업",
    xaxis_title="날짜",
    yaxis_title=y_label,
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("기업별 기간 수익률")
return_df = (
    returns.sort_values(ascending=False)
    .reset_index()
    .rename(columns={"index": "기업", 0: "수익률(%)"})
)
bar_fig = px.bar(return_df, x="수익률(%)", y="기업", orientation="h", title="선택 기간 수익률 순위")
bar_fig.update_layout(yaxis={"categoryorder": "total ascending"})
st.plotly_chart(bar_fig, use_container_width=True)

st.subheader("요약 테이블")
snapshot["시가총액"] = snapshot["시가총액"].apply(lambda x: f"${x/1e12:.2f}T" if pd.notna(x) else "N/A")
snapshot["현재가"] = snapshot["현재가"].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "N/A")
summary = snapshot.merge(
    returns.rename("기간 수익률(%)").reset_index().rename(columns={"index": "기업"}),
    on="기업",
    how="left",
)
summary["기간 수익률(%)"] = summary["기간 수익률(%)"].map(lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A")
st.dataframe(summary, use_container_width=True, hide_index=True)

if show_volume:
    st.subheader("거래량")
    volume = load_volume(selected_tickers, period).rename(columns=company_by_ticker)
    volume_long = volume.reset_index().melt(id_vars="Date", var_name="기업", value_name="거래량")
    volume_fig = px.line(volume_long, x="Date", y="거래량", color="기업", title="일별 거래량")
    volume_fig.update_layout(hovermode="x unified", xaxis_title="날짜", yaxis_title="거래량")
    st.plotly_chart(volume_fig, use_container_width=True)

st.info("배포 후 데이터가 안 보이면 requirements.txt 설치 여부와 Streamlit Cloud secrets/network 상태를 확인하세요.")
