# backend/core/data_handler.py
# yfinance 완전 삭제 → Finnhub + Alpha Vantage + Google News RSS

import httpx
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, List
from urllib.parse import quote_plus
import os
from datetime import datetime
import pandas_ta as ta

# 환경변수에서 키 가져오기 (Render에서 설정할거임)
FINNHUB_KEY = os.getenv("FINNHUB_KEY")  # 필수!
ALPHA_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")  # 보조용 (없어도 됨)

# Finnhub 기본 엔드포인트
FINNHUB_BASE = "https://finnhub.io/api/v1"

# 한국 주식 티커 정규화 (005930 → 005930:KRX)
def normalize_ticker(ticker: str) -> str:
    ticker = ticker.upper().replace(".KS", "").replace(".KQ", "")
    if ticker.isdigit() and len(ticker) == 6:
        return f"{ticker}:KRX"
    return ticker

async def _finnhub_get(url: str, params: dict = None):
    if not FINNHUB_KEY:
        return None
    params = params or {}
    params["token"] = FINNHUB_KEY
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, params=params)
        if r.status_code == 200:
            return r.json()
        return None

def get_historical_data(ticker: str, period: str = "3mo") -> Optional[pd.DataFrame]:
    ticker_norm = normalize_ticker(ticker)
    # Finnhub은 일봉 최대 1년까지 무료로 줌
    url = f"{FINNHUB_BASE}/stock/candle"
    params = {
        "symbol": ticker_norm,
        "resolution": "D",
        "from": int(datetime(2020, 1, 1).timestamp()),  # 넉넉하게
        "to": int(datetime.now().timestamp()),
    }
    data = requests.get(url, params=params).json()
    if data.get("s") != "ok":
        return None

    df = pd.DataFrame({
        "Date": pd.to_datetime(data["t"], unit="s"),
        "Open": data["o"],
        "High": data["h"],
        "Low": data["l"],
        "Close": data["c"],
        "Volume": data["v"],
    }).set_index("Date")
    return df.tail(90)  # 3개월치만

def get_stock_info(ticker: str) -> Dict[str, Any]:
    ticker_norm = normalize_ticker(ticker)
    # 1. 현재가 + 기본 정보
    quote = requests.get(f"{FINNHUB_BASE}/quote", params={"symbol": ticker_norm}).json()
    profile = requests.get(f"{FINNHUB_BASE}/stock/profile2", params={"symbol": ticker_norm}).json()

    if not quote.get("c"):
        return {"name": ticker, "current_price": None}

    return {
        "name": profile.get("name", ticker),
        "current_price": quote["c"],
        "regularMarketPrice": quote["c"],
        "previous_close": quote["pc"],
        "currency": profile.get("currency", "USD"),
        "exchange": profile.get("exchange", ""),
        "sector": profile.get("finnhubIndustry"),
        "market_cap": profile.get("marketCapitalization"),
        "per": None,  # 무료 플랜에선 안 줌 → 나중에 유료로
        "pbr": None,
        "roe": None,
        "dividend_yield": None,
        "longBusinessSummary": profile.get("description", ""),
        "fullTimeEmployees": profile.get("employeeTotal"),
        "website": profile.get("weburl"),
    }

def get_news_items(ticker: str, limit: int = 6, lang: str = "en") -> List[Dict[str, Any]]:
    # Finnhub 뉴스 (무료로 60 calls/min)
    ticker_norm = normalize_ticker(ticker)
    params = {
        "symbol": ticker_norm if ":" in ticker_norm else ticker,
        "from": (datetime.now().date() - pd.Timedelta(days=7)).isoformat(),
        "to": datetime.now().date().isoformat(),
    }
    news = requests.get(f"{FINNHUB_BASE}/company-news", params=params).json()

    items = []
    for n in news[:limit]:
        if n.get("headline") and n.get("url"):
            items.append({
                "title": n["headline"],
                "link": n["url"],
                "publisher": n.get("source"),
                "published_at": datetime.fromtimestamp(n["datetime"]).isoformat() if n.get("datetime") else None,
            })
    # 부족하면 Google News 보완 (기존 코드 그대로)
    if len(items) < limit:
        # 기존 Google News RSS 코드 복사 (너가 이미 잘 짜놨던거 그대로)
        try:
            query = quote_plus(ticker)
            url = f"https://news.google.com/rss/search?q={query}&hl={lang}&gl=KR"
            resp = requests.get(url, timeout=5)
            if resp.ok:
                root = ET.fromstring(resp.content)
                for item in root.findall('.//item')[:limit-len(items)]:
                    title = item.find('title').text
                    link = item.find('link').text
                    items.append({"title": title, "link": link, "publisher": "Google News"})
        except:
            pass
    return items[:limit]

def _calc_change(ticker: str) -> Optional[Dict[str, Any]]:
    ticker_norm = normalize_ticker(ticker)
    quote = requests.get(f"{FINNHUB_BASE}/quote", params={"symbol": ticker_norm}).json()
    if not quote.get("c"):
        return None
    price = quote["c"]
    prev = quote["pc"]
    change = price - prev
    pct = (change / prev) * 100 if prev else 0
    return {"price": price, "change": change, "change_pct": pct}

def get_market_snapshot() -> Dict[str, Any]:
    indices = {
        "SPX": "^GSPC",
        "NASDAQ": "^IXIC",
        "KOSPI": "000001:KRX",  # KOSPI는 이렇게
        "USDKRW": "USD/KRW",
    }
    result = {}
    for name, sym in indices.items():
        norm = normalize_ticker(sym)
        data = _calc_change(norm if norm else sym)
        if data:
            result[name] = data
    return result

def get_global_headlines(limit: int = 6) -> List[Dict[str, Any]]:
    # Finnhub 시장 뉴스
    news = requests.get(f"{FINNHUB_BASE}/news", params={"category": "general"}).json()
    return [
        {
            "title": n["headline"],
            "link": n["url"],
            "publisher": n.get("source"),
            "published_at": datetime.fromtimestamp(n["datetime"]).isoformat() if n.get("datetime") else None,
        }
        for n in news[:limit]
        if n.get("headline") and n.get("url")
    ]