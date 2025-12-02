# backend/core/data_handler.py
# Finnhub + Alpha Vantage (5키) 통합, 동기 코드 + 간단 캐시

import requests
import pandas as pd
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, List
from urllib.parse import quote_plus
import os
from datetime import datetime, timedelta
import time

# ==================== 환경변수 ====================
FINNHUB_KEY = os.getenv("FINNHUB_KEY")
ALPHA_KEYS = [os.getenv(f"ALPHA_VANTAGE_KEY{i}") for i in range(1, 6) if os.getenv(f"ALPHA_VANTAGE_KEY{i}")]

# ==================== 캐시 ====================
CACHE: Dict[str, tuple] = {}
CACHE_TTL = 45  # 45초

def _cache_get(key: str):
    if key in CACHE:
        ts, data = CACHE[key]
        if time.time() - ts < CACHE_TTL:
            return data
    return None

def _cache_set(key: str, data):
    CACHE[key] = (time.time(), data)

# ==================== 심볼 정규화 ====================
def normalize_symbol(ticker: str) -> str:
    norm = ticker.upper()
    # 한국 6자리 숫자코드 → .KS
    base = norm.replace(".KQ", "").replace(".KS", "")
    if len(base) == 6 and base.isdigit():
        return f"{base}.KS"
    return norm

# ==================== Finnhub ====================
def finnhub_quote(symbol: str) -> Optional[dict]:
    if not FINNHUB_KEY:
        return None
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": symbol, "token": FINNHUB_KEY},
            timeout=8,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("c") and data["c"] != 0:
                return {"price": data["c"], "prev": data.get("pc", data["c"]), "source": "finnhub"}
    except Exception:
        return None
    return None

def finnhub_historical(symbol: str) -> Optional[pd.DataFrame]:
    if not FINNHUB_KEY:
        return None
    try:
        params = {
            "symbol": symbol,
            "resolution": "D",
            "from": int((datetime.now() - timedelta(days=120)).timestamp()),
            "to": int(datetime.now().timestamp()),
            "token": FINNHUB_KEY,
        }
        data = requests.get("https://finnhub.io/api/v1/stock/candle", params=params, timeout=10).json()
        if data.get("s") == "ok":
            df = pd.DataFrame(
                {
                    "Date": pd.to_datetime(data["t"], unit="s"),
                    "Open": data["o"],
                    "High": data["h"],
                    "Low": data["l"],
                    "Close": data["c"],
                    "Volume": data["v"],
                }
            ).set_index("Date")
            return df.sort_index()
    except Exception:
        return None
    return None

def finnhub_profile(symbol: str) -> Dict[str, Any]:
    if not FINNHUB_KEY:
        return {}
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/stock/profile2",
            params={"symbol": symbol, "token": FINNHUB_KEY},
            timeout=8,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        return {}
    return {}

def finnhub_company_news(symbol: str, days: int = 7) -> List[Dict[str, Any]]:
    if not FINNHUB_KEY:
        return []
    try:
        today = datetime.utcnow().date()
        frm = (today - timedelta(days=days)).isoformat()
        to = today.isoformat()
        r = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": symbol, "from": frm, "to": to, "token": FINNHUB_KEY},
            timeout=8,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        return []
    return []

# ==================== Alpha Vantage ====================
def alpha_quote(symbol: str) -> Optional[dict]:
    if not ALPHA_KEYS:
        return None
    for key in ALPHA_KEYS:
        try:
            r = requests.get(
                "https://www.alphavantage.co/query",
                params={"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": key},
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json().get("Global Quote", {})
                if data.get("05. price"):
                    price = float(data["05. price"])
                    prev = float(data.get("08. previous close", price))
                    return {"price": price, "prev": prev, "source": "alpha"}
        except Exception:
            continue
    return None

def alpha_historical(symbol: str) -> Optional[pd.DataFrame]:
    if not ALPHA_KEYS:
        return None
    for key in ALPHA_KEYS:
        try:
            r = requests.get(
                "https://www.alphavantage.co/query",
                params={"function": "TIME_SERIES_DAILY", "symbol": symbol, "outputsize": "compact", "apikey": key},
                timeout=15,
            )
            data = r.json()
            ts = data.get("Time Series (Daily)")
            if ts:
                df = pd.DataFrame.from_dict(ts, orient="index")
                df = df.astype(float)
                df.index = pd.to_datetime(df.index)
                df = df.rename(
                    columns={
                        "1. open": "Open",
                        "2. high": "High",
                        "3. low": "Low",
                        "4. close": "Close",
                        "5. volume": "Volume",
                    }
                )
                return df.sort_index().tail(90)
        except Exception:
            continue
    return None

# ==================== 통합 헬퍼 ====================
def get_current_price(ticker: str) -> Optional[dict]:
    symbol = normalize_symbol(ticker)
    cache_key = f"price:{symbol}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    result = finnhub_quote(symbol) or alpha_quote(symbol)
    if result:
        change = result["price"] - result["prev"]
        pct = (change / result["prev"]) * 100 if result["prev"] else 0
        final = {
            "price": round(result["price"], 2),
            "change": round(change, 2),
            "change_pct": round(pct, 2),
            "source": result["source"],
        }
        _cache_set(cache_key, final)
        return final
    return None

def get_historical_data(ticker: str, period: str = "3mo") -> Optional[pd.DataFrame]:
    symbol = normalize_symbol(ticker)
    df = finnhub_historical(symbol)
    if df is None:
        df = alpha_historical(symbol)
    return df

def get_stock_info(ticker: str) -> Dict[str, Any]:
    symbol = normalize_symbol(ticker)
    quote = finnhub_quote(symbol) or alpha_quote(symbol) or {}
    profile = finnhub_profile(symbol)
    return {
        "name": profile.get("name", ticker),
        "current_price": quote.get("price"),
        "regular_market_price": quote.get("price"),
        "previous_close": quote.get("prev"),
        "currency": profile.get("currency", "USD"),
        "exchange": profile.get("exchange", ""),
        "sector": profile.get("finnhubIndustry"),
        "market_cap": profile.get("marketCapitalization"),
        "per": None,
        "pbr": None,
        "roe": None,
        "dividend_yield": None,
        "longBusinessSummary": profile.get("description", ""),
        "fullTimeEmployees": profile.get("employeeTotal"),
        "website": profile.get("weburl"),
    }

def get_news_items(ticker: str, limit: int = 6, lang: str = "en") -> List[Dict[str, Any]]:
    symbol = normalize_symbol(ticker)
    items: List[Dict[str, Any]] = []

    for n in finnhub_company_news(symbol):
        if n.get("headline") and n.get("url"):
            items.append(
                {
                    "title": n["headline"],
                    "link": n["url"],
                    "publisher": n.get("source"),
                    "published_at": datetime.fromtimestamp(n["datetime"]).isoformat() if n.get("datetime") else None,
                }
            )
        if len(items) >= limit:
            break

    # 부족하면 Google News RSS 보완
    if len(items) < limit:
        try:
            region = "KR" if lang.startswith("ko") else "US"
            query = quote_plus(ticker)
            url = f"https://news.google.com/rss/search?q={query}&hl={lang}&gl={region}"
            resp = requests.get(url, timeout=5)
            if resp.ok:
                root = ET.fromstring(resp.content)
                for item in root.findall(".//item"):
                    title_el = item.find("title")
                    link_el = item.find("link")
                    if title_el is None or link_el is None:
                        continue
                    items.append({"title": title_el.text, "link": link_el.text, "publisher": "Google News"})
                    if len(items) >= limit:
                        break
        except Exception:
            pass
    return items[:limit]

def _calc_change(ticker: str) -> Optional[Dict[str, Any]]:
    quote = get_current_price(ticker)
    if not quote:
        return None
    return {"price": quote["price"], "change": quote["change"], "change_pct": quote["change_pct"]}

def get_market_snapshot() -> Dict[str, Any]:
    indices = {
        "SPX": "SPY",
        "NASDAQ": "QQQ",
        "KOSPI": "069500.KS",  # 코스피200 ETF 대용
        "USDKRW": "USD/KRW",
    }
    result = {}
    for name, sym in indices.items():
        data = _calc_change(sym)
        if data:
            result[name] = data
    return result

def get_global_headlines(limit: int = 6) -> List[Dict[str, Any]]:
    if not FINNHUB_KEY:
        return []
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/news",
            params={"category": "general", "token": FINNHUB_KEY},
            timeout=8,
        )
        news = r.json() if r.status_code == 200 else []
    except Exception:
        news = []
    items = []
    for n in news[:limit]:
        if n.get("headline") and n.get("url"):
            items.append(
                {
                    "title": n["headline"],
                    "link": n["url"],
                    "publisher": n.get("source"),
                    "published_at": datetime.fromtimestamp(n["datetime"]).isoformat() if n.get("datetime") else None,
                }
            )
    return items
