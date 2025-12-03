# backend/core/data_handler.py
# Finnhub + Alpha Vantage (5키) 통합, 동기 코드 + 간단 캐시

import os
import re
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import quote_plus

import pandas as pd
import requests
import xml.etree.ElementTree as ET

# ==================== 환경변수 ====================
FINNHUB_KEY = os.getenv("FINNHUB_KEY")
ALPHA_KEYS = [os.getenv(f"ALPHA_VANTAGE_KEY{i}") for i in range(1, 6) if os.getenv(f"ALPHA_VANTAGE_KEY{i}")]
HAS_PUBLIC_YAHOO = True  # 무료 quote/chart 엔드포인트 사용
NO_REMOTE_DATA = False  # Yahoo 퍼블릭 데이터를 항상 시도하므로 완전 오프라인이 아님
NO_KEYED_DATA = not FINNHUB_KEY and not ALPHA_KEYS

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
    if norm == "USD/KRW":
        return "KRW=X"
    # 한국 6자리 숫자코드 → .KS
    base = norm.replace(".KQ", "").replace(".KS", "")
    if len(base) == 6 and base.isdigit():
        return f"{base}.KS"
    return norm

# ==================== Yahoo Finance (크럼 없는 공개 엔드포인트) ====================
def yahoo_quote(symbol: str) -> Optional[dict]:
    """
    무료 공개 엔드포인트를 사용해 현재가/기본 정보 조회.
    별도 크럼(crumb)이나 쿠키가 필요 없는 quote API만 사용한다.
    """
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v7/finance/quote",
            params={"symbols": symbol},
            timeout=6,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if r.status_code != 200:
            return None
        results = r.json().get("quoteResponse", {}).get("result", [])
        if not results:
            return None
        q = results[0]
        price = q.get("regularMarketPrice")
        prev = q.get("regularMarketPreviousClose", price)
        if price is None:
            return None
        return {
            "price": float(price),
            "prev": float(prev) if prev is not None else None,
            "source": "yahoo",
            "currency": q.get("currency"),
            "name": q.get("longName") or q.get("shortName") or symbol,
            "exchange": q.get("fullExchangeName") or q.get("exchange"),
            "market_cap": q.get("marketCap"),
            "per": q.get("trailingPE"),
            "pbr": q.get("priceToBook"),
            "dividend_yield": q.get("trailingAnnualDividendYield"),
            "industry": q.get("industry"),
            "sector": q.get("sector"),
            "employees": q.get("fullTimeEmployees"),
            "website": q.get("website"),
        }
    except Exception:
        return None


def yahoo_history(symbol: str, range_str: str = "6mo") -> Optional[pd.DataFrame]:
    """
    크럼이 필요 없는 chart API로 일별 시계열을 수집한다.
    6개월 구간이면 90일 이상 데이터를 확보할 수 있어 지표 계산이 가능하다.
    """
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"range": range_str, "interval": "1d", "events": "div,split"},
            timeout=8,
        )
        if r.status_code != 200:
            return None
        chart = r.json().get("chart", {})
        results = chart.get("result") or []
        if not results:
            return None
        result = results[0]
        ts = result.get("timestamp")
        quote = (result.get("indicators") or {}).get("quote", [{}])[0]
        if not ts or not quote.get("close"):
            return None
        df = pd.DataFrame(
            {
                "Date": pd.to_datetime(ts, unit="s"),
                "Open": quote.get("open"),
                "High": quote.get("high"),
                "Low": quote.get("low"),
                "Close": quote.get("close"),
                "Volume": quote.get("volume"),
            }
        )
        df = df.dropna(subset=["Close"])
        return df.set_index("Date").sort_index()
    except Exception:
        return None


def yahoo_profile(symbol: str) -> Dict[str, Any]:
    """
    quoteSummary의 assetProfile 모듈을 통해 섹터/산업/홈페이지/직원수 등을 보완한다.
    """
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}",
            params={"modules": "assetProfile"},
            timeout=6,
        )
        if r.status_code != 200:
            return {}
        result = (r.json().get("quoteSummary", {}) or {}).get("result") or []
        profile = result[0].get("assetProfile", {}) if result else {}
        return {
            "industry": profile.get("industry"),
            "sector": profile.get("sector"),
            "website": profile.get("website"),
            "employees": profile.get("fullTimeEmployees"),
            "summary": profile.get("longBusinessSummary"),
            "country": profile.get("country"),
        }
    except Exception:
        return {}

# ==================== Finnhub ====================
def finnhub_quote(symbol: str) -> Optional[dict]:
    if not FINNHUB_KEY:
        return None
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": symbol, "token": FINNHUB_KEY},
            timeout=4,
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
        data = requests.get("https://finnhub.io/api/v1/stock/candle", params=params, timeout=6).json()
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
            timeout=5,
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
            timeout=6,
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
                timeout=6,
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


def stooq_quote(symbol: str) -> Optional[dict]:
    """무료 stooq API (미국/일부 글로벌). 한국 종목은 지원하지 않음."""
    base = symbol.lower()
    if "." not in base:
        base = f"{base}.us"
    try:
        r = requests.get(
            "https://stooq.pl/q/l/",
            params={"s": base, "f": "sd2t2ohlcv", "h": "", "e": "json"},
            timeout=6,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if r.status_code == 200:
            data = r.json().get("symbols", [])
            if data and data[0].get("close"):
                price = float(data[0]["close"])
                prev = float(data[0].get("open") or price)
                return {"price": price, "prev": prev, "source": "stooq"}
    except Exception:
        return None
    return None


def naver_quote(symbol: str) -> Optional[dict]:
    """네이버 금융 HTML 파싱 (KR 6자리 코드만)."""
    base = symbol.replace(".KS", "").replace(".KQ", "")
    if not (len(base) == 6 and base.isdigit()):
        return None
    try:
        r = requests.get(
            "https://finance.naver.com/item/main.nhn",
            params={"code": base},
            timeout=6,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if r.status_code != 200:
            return None
        html = r.text
        # 기본 시세는 blind 클래스 숫자 첫 번째를 사용
        m = re.search(r'no_today[^>]*>.*?<span class="blind">([0-9,\.]+)</span>', html, re.S)
        if not m:
            return None
        price = float(m.group(1).replace(",", ""))
        # 전일 종가 추출 (전일가 테이블)
        prev_match = re.search(r'전일가[^>]*?blind">([0-9,\.]+)</span>', html)
        prev = float(prev_match.group(1).replace(",", "")) if prev_match else price
        return {"price": price, "prev": prev, "source": "naver"}
    except Exception:
        return None
    return None

def alpha_historical(symbol: str) -> Optional[pd.DataFrame]:
    if not ALPHA_KEYS:
        return None
    for key in ALPHA_KEYS:
        try:
            r = requests.get(
                "https://www.alphavantage.co/query",
                params={"function": "TIME_SERIES_DAILY", "symbol": symbol, "outputsize": "compact", "apikey": key},
                timeout=8,
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

    result = (
        finnhub_quote(symbol)
        or alpha_quote(symbol)
        or yahoo_quote(symbol)
        or (naver_quote(symbol) if symbol.endswith(".KS") or symbol.endswith(".KQ") else None)
        or stooq_quote(symbol)
    )
    if result:
        prev_val = result.get("prev")
        base_prev = prev_val if prev_val not in (None, 0) else result["price"]
        change = result["price"] - base_prev
        pct = (change / base_prev) * 100 if base_prev else 0
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
    df = finnhub_historical(symbol) or alpha_historical(symbol) or yahoo_history(symbol)
    return df

def get_stock_info(ticker: str) -> Dict[str, Any]:
    symbol = normalize_symbol(ticker)
    quote = (
        finnhub_quote(symbol)
        or alpha_quote(symbol)
        or yahoo_quote(symbol)
        or (naver_quote(symbol) if symbol.endswith(".KS") or symbol.endswith(".KQ") else None)
        or stooq_quote(symbol)
        or {}
    )
    profile_finn = finnhub_profile(symbol)
    profile_yahoo = yahoo_profile(symbol)
    profile = {**profile_yahoo, **profile_finn}
    return {
        "name": profile.get("name") or quote.get("name") or ticker,
        "current_price": quote.get("price"),
        "regular_market_price": quote.get("price"),
        "previous_close": quote.get("prev"),
        "currency": profile.get("currency") or quote.get("currency") or "USD",
        "exchange": profile.get("exchange") or quote.get("exchange") or "",
        "sector": profile.get("finnhubIndustry") or profile.get("sector"),
        "industry": profile.get("industry"),
        "market_cap": profile.get("marketCapitalization") or quote.get("market_cap"),
        "per": quote.get("per"),
        "pbr": quote.get("pbr"),
        "roe": None,
        "dividend_yield": quote.get("dividend_yield"),
        "summary": profile.get("summary") or profile.get("description", ""),
        "longBusinessSummary": profile.get("description", "") or profile.get("summary", ""),
        "fullTimeEmployees": profile.get("employeeTotal") or profile.get("employees"),
        "employees": profile.get("employeeTotal") or profile.get("employees"),
        "website": profile.get("weburl") or profile.get("website"),
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
    start = time.time()
    for name, sym in indices.items():
        if time.time() - start > 6:
            # 오래 걸리면 남은 지표는 건너뛰고 빠르게 반환
            break
        try:
            data = _calc_change(sym)
        except Exception:
            data = None
        if data:
            result[name] = data
    if not result:
        # 모든 소스 실패 시 최소 더미 값을 반환해 프론트에서 에러를 띄우지 않도록 한다.
        result = {
            "SPX": {"price": 0.0, "change": 0.0, "change_pct": 0.0},
            "NASDAQ": {"price": 0.0, "change": 0.0, "change_pct": 0.0},
            "KOSPI": {"price": 0.0, "change": 0.0, "change_pct": 0.0},
            "USDKRW": {"price": 0.0, "change": 0.0, "change_pct": 0.0},
        }
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
