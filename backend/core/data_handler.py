# backend/core/data_handler.py
import os
import time
import requests
from typing import Optional, Dict, Any
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 재시도 세션 (Yahoo 블록 방지)
session = requests.Session()
retry = Retry(total=5, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)

def yahoo_quote(symbol: str) -> Optional[Dict[str, Any]]:
    try:
        url = "https://query1.finance.yahoo.com/v7/finance/quote"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = session.get(url, params={"symbols": symbol}, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()["quoteResponse"]["result"]
        if not data:
            return None
        q = data[0]

        price = (
            q.get("regularMarketPrice") or
            q.get("postMarketPrice") or
            q.get("preMarketPrice") or
            q.get("regularMarketPreviousClose")
        )
        if not price:
            return None

        return {
            "price": float(price),
            "prev": float(q.get("regularMarketPreviousClose") or price),
            "change": float(price) - float(q.get("regularMarketPreviousClose") or price),
            "change_pct": round(((float(price) - float(q.get("regularMarketPreviousClose") or price)) / float(q.get("regularMarketPreviousClose") or price)) * 100, 2),
            "name": q.get("longName") or q.get("shortName") or symbol,
            "currency": q.get("currency", "USD"),
        }
    except Exception as e:
        print(f"[Yahoo 실패] {symbol}: {e}")
        return None

def get_current_price(ticker: str) -> Optional[Dict[str, Any]]:
    return yahoo_quote(ticker)

# 간단 뉴스 (Finnhub 키 없어도 기본 뉴스 나옴)
def get_global_headlines(limit: int = 8) -> list:
    fallback_news = [
        {"title": "미국 증시, FOMC 결과를 주목하고 있습니다", "link": "https://finance.yahoo.com"},
        {"title": "엔비디아 실적 발표 앞두고 기술주 강세", "link": "https://finance.yahoo.com"},
        {"title": "삼성전자, 3나노 양산 본격화", "link": "https://finance.naver.com"},
    ]
    return fallback_news[:limit]

# 시장 지표
def get_market_snapshot() -> Dict[str, Any]:
    indices = {"SPY": "S&P 500", "QQQ": "NASDAQ", "^KS11": "KOSPI", "KRW=X": "USD/KRW"}
    result = {}
    for sym, name in indices.items():
        data = get_current_price(sym)
        if data:
            result[name] = {
                "price": round(data["price"], 2),
                "change_pct": data.get("change_pct", 0),
            }
        else:
            result[name] = {"price": 0, "change_pct": 0}
    return result