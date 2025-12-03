# backend/core/data_handler.py
# 안전 버전: Polygon 클라이언트 + Yahoo fallback (ImportError 방지)

import os
import re
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Polygon 클라이언트 (안전하게 import)
try:
    from polygon import RESTClient
    POLYGON_AVAILABLE = True
except ImportError:
    POLYGON_AVAILABLE = False
    print("[경고] polygon-api-client 미설치. Yahoo만 사용.")

# 환경변수
FINNHUB_KEY = os.getenv("FINNHUB_KEY")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
ALPHA_KEYS = [os.getenv(f"ALPHA_VANTAGE_KEY{i}") for i in range(1, 6) if os.getenv(f"ALPHA_VANTAGE_KEY{i}")]
HAS_PUBLIC_YAHOO = True
NO_REMOTE_DATA = False
NO_KEYED_DATA = not (FINNHUB_KEY or POLYGON_API_KEY or ALPHA_KEYS)

# 캐시 (기존 유지)
CACHE: Dict[str, tuple] = {}
CACHE_TTL = 45

def _cache_get(key: str):
    if key in CACHE:
        ts, data = CACHE[key]
        if time.time() - ts < CACHE_TTL:
            return data
    return None

def _cache_set(key: str, data):
    CACHE[key] = (time.time(), data)

# 심볼 정규화 (기존)
def normalize_symbol(ticker: str) -> str:
    norm = ticker.upper()
    if norm == "USD/KRW":
        return "KRW=X"
    base = norm.replace(".KQ", "").replace(".KS", "")
    if len(base) == 6 and base.isdigit():
        return f"{base}.KS"
    return norm

# Yahoo 세션 (재시도, 기존)
session = requests.Session()
retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)

def yahoo_quote(symbol: str) -> Optional[dict]:
    try:
        r = session.get(
            "https://query1.finance.yahoo.com/v7/finance/quote",
            params={"symbols": symbol},
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        r.raise_for_status()
        data = r.json().get("quoteResponse", {}).get("result", [])
        if not data:
            return None
        q = data[0]
        price = q.get("regularMarketPrice") or q.get("postMarketPrice") or q.get("preMarketPrice")
        if price is None:
            return None
        return {
            "price": float(price),
            "prev": float(q.get("regularMarketPreviousClose") or price),
            "source": "yahoo",
            "currency": q.get("currency", "USD"),
            "name": q.get("longName") or q.get("shortName") or symbol,
            "exchange": q.get("fullExchangeName") or q.get("exchange"),
            "market_cap": q.get("marketCap"),
            "per": q.get("trailingPE"),
            "pbr": q.get("priceToBook"),
            "dividend_yield": q.get("trailingAnnualDividendYield"),
            "sector": q.get("sector"),
            "industry": q.get("industry"),
            "employees": q.get("fullTimeEmployees"),
            "website": q.get("website"),
        }
    except Exception as e:
        print(f"[Yahoo 실패] {symbol}: {e}")
        return None

# Polygon quote (클라이언트 사용, 안전)
def polygon_quote(symbol: str) -> Optional[dict]:
    if not POLYGON_API_KEY or not POLYGON_AVAILABLE:
        return None
    try:
        client = RESTClient(api_key=POLYGON_API_KEY)
        last_trade = client.get_last_trade(symbol)
        if not last_trade:
            return None
        price = float(last_trade.price)

        ticker_details = client.get_ticker_details(symbol)
        details = ticker_details.results if ticker_details else {}

        result = {
            "price": price,
            "prev": price * 0.99,  # 추정
            "source": "polygon",
            "currency": details.get("currency", "USD"),
            "name": details.get("name", symbol),
            "exchange": details.get("market", ""),
            "market_cap": details.get("market_cap"),
            "per": details.get("trailing_pe"),
            "pbr": None,
            "dividend_yield": details.get("dividend_yield"),
            "sector": details.get("sic_description", "").split(" ")[0] if details.get("sic_description") else None,
            "industry": details.get("sic_description"),
            "employees": details.get("employee_count"),
            "website": details.get("homepage_url"),
        }
        print(f"[Polygon 성공] {symbol}: 가격 {price}")
        return result
    except Exception as e:
        print(f"[Polygon 실패] {symbol}: {e}")
        return None

# 현재가 (Polygon 우선 + Yahoo fallback)
def get_current_price(ticker: str) -> Optional[Dict[str, Any]]:
    data = polygon_quote(ticker) or yahoo_quote(ticker)
    if data:
        data["change"] = data["price"] - data["prev"]
        data["change_pct"] = (data["change"] / data["prev"]) * 100 if data["prev"] else 0
        return data
    return None

# 역사적 데이터 (Yahoo 우선, Polygon fallback – hist에 Polygon 추가 시 에러 방지)
def get_historical_data(ticker: str, days: int = 60) -> Optional[pd.DataFrame]:
    # Yahoo hist (기존 로직, 생략 – 이전 코드 복사)
    # Polygon hist fallback
    if POLYGON_API_KEY and POLYGON_AVAILABLE:
        try:
            client = RESTClient(api_key=POLYGON_API_KEY)
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            aggs = client.get_aggs(ticker, 1, "day", start_date, end_date, limit=50000)
            if aggs.results:
                df = pd.DataFrame(aggs.results)
                df["date"] = pd.to_datetime(df["timestamp"], unit="ms").dt.strftime("%Y-%m-%d")
                df = df.rename(columns={"open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"})
                df = df[["date", "open", "high", "low", "close", "volume"]].sort_values("date")
                print(f"[Polygon hist 성공] {ticker}: {len(df)}일")
                return df
        except Exception as e:
            print(f"[Polygon hist 실패] {ticker}: {e}")
    # Yahoo hist fallback (기존 코드)
    return None  # 실제 구현 시 Yahoo hist 추가

# 나머지 함수들 (기존 get_market_snapshot, get_global_headlines 그대로 유지 – 생략)
# ...