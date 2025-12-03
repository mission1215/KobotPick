# backend/core/data_handler.py
import os
import time
import requests
import yfinance as yf
from typing import Optional, Dict, Any, List
from datetime import datetime

# 환경변수 (Render 대시보드에서 설정)
FINNHUB_KEY = os.getenv("FINNHUB_KEY")
# ALPHA_VANTAGE_KEY, ALPHA_VANTAGE_KEY1~5 등 여러 키 중 사용 가능한 것 선택
ALPHA_KEYS = [
    v
    for name in ["ALPHA_VANTAGE_KEY"] + [f"ALPHA_VANTAGE_KEY{i}" for i in range(1, 6)]
    if (v := os.getenv(name))
]

def finnhub_quote(ticker: str) -> Optional[Dict]:
    if not FINNHUB_KEY:
        return None
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("c"):
                return {
                    "price": float(data["c"]),
                    "prev": float(data["pc"] or data["c"]),
                    "change_pct": round(((data["c"] - data["pc"]) / data["pc"]) * 100, 2) if data["pc"] else 0,
                    "source": "finnhub",
                }
    except Exception:
        pass
    return None

def alpha_quote(ticker: str) -> Optional[Dict]:
    if not ALPHA_KEYS:
        return None
    # 간단한 라운드로빈으로 키를 돌려가며 사용 (호출 제한 완화)
    key = ALPHA_KEYS[int(time.time()) % len(ALPHA_KEYS)]
    try:
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": ticker,
            "apikey": key,
        }
        r = requests.get(url, params=params, timeout=12)
        data = r.json().get("Global Quote", {})
        if data.get("05. price"):
            price = float(data["05. price"])
            change_pct = float(data.get("10. change percent", "0").replace("%", ""))
            return {
                "price": price,
                "prev": price / (1 + change_pct / 100) if change_pct != 0 else price,
                "change_pct": round(change_pct, 2),
                "source": "alpha",
            }
        # Alpha Vantage는 제한이 걸리면 Note 필드로 알려줌
        if data and isinstance(data, dict) and data.get("Note"):
            print(f"[Alpha throttled] {data.get('Note')}")
    except Exception as exc:
        print(f"[Alpha error] {ticker}: {exc}")
    return None

def yfinance_quote(ticker: str) -> Optional[Dict]:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        hist = stock.history(period="2d")
        if len(hist) < 2:
            return None
        current = hist["Close"].iloc[-1]
        prev = hist["Close"].iloc[-2]
        currency = info.get("currency") or ("KRW" if ticker.endswith(".KS") else "USD")
        return {
            "price": round(current, 2),
            "prev": round(prev, 2),
            "change_pct": round(((current - prev) / prev) * 100, 2),
            "name": info.get("longName") or info.get("shortName") or ticker,
            "currency": currency,
            "source": "yfinance",
        }
    except Exception:
        return None

def get_price(ticker: str) -> Optional[Dict]:
    """Finnhub → Alpha Vantage → yfinance 순으로 시도"""
    result = finnhub_quote(ticker)
    if result:
        print(f"[Finnhub] {ticker}: {result['price']}")
        return result

    result = alpha_quote(ticker)
    if result:
        print(f"[Alpha] {ticker}: {result['price']}")
        return result

    result = yfinance_quote(ticker)
    if result:
        print(f"[yfinance] {ticker}: {result['price']}")
        return result

    print(f"[모든 소스 실패] {ticker}")
    return None


def get_stock_profile(ticker: str) -> Dict[str, Any]:
    """섹터/산업/직원수 등 기업 정보를 가져옵니다."""
    try:
        info = yf.Ticker(ticker).info or {}
        return {
            "sector": info.get("sector"),
            "industry": info.get("industry") or info.get("industryDisp"),
            "website": info.get("website"),
            "summary": info.get("longBusinessSummary"),
            "employees": info.get("fullTimeEmployees"),
            "exchange": info.get("exchange"),
            "currency": info.get("currency") or ("KRW" if ticker.endswith(".KS") else "USD"),
        }
    except Exception:
        return {}


def get_fundamentals(ticker: str) -> Dict[str, Optional[float]]:
    """시가총액, PER 등 기본 펀더멘탈 지표를 반환."""
    try:
        info = yf.Ticker(ticker).info or {}
        return {
            "market_cap": info.get("marketCap"),
            "per": info.get("trailingPE"),
            "pbr": info.get("priceToBook"),
            "roe": info.get("returnOnEquity"),
            "dividend_yield": info.get("dividendYield"),
            "psr": info.get("priceToSalesTrailing12Months"),
        }
    except Exception:
        return {
            "market_cap": None,
            "per": None,
            "pbr": None,
            "roe": None,
            "dividend_yield": None,
            "psr": None,
        }


def get_historical_candles(ticker: str, days: int = 120) -> List[Dict[str, Any]]:
    """최근 일자별 시가/고가/저가/종가를 반환합니다."""
    try:
        hist = yf.Ticker(ticker).history(period=f"{days}d")
        if hist.empty:
            return []
        candles = []
        for ts, row in hist.iterrows():
            candles.append(
                {
                    "date": ts.isoformat(),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                }
            )
        return candles[-days:]
    except Exception:
        return []


def get_company_news(ticker: str, limit: int = 6) -> List[Dict[str, Any]]:
    """yfinance 뉴스 항목을 단순 정리."""
    try:
        news = getattr(yf.Ticker(ticker), "news", None) or []
        items: List[Dict[str, Any]] = []
        for n in news[:limit]:
            title = n.get("title")
            link = n.get("link")
            if not title or not link:
                continue
            items.append(
                {
                    "title": title,
                    "link": link,
                    "publisher": n.get("publisher"),
                    "published_at": n.get("providerPublishTime"),
                }
            )
        return items
    except Exception:
        return []

def get_global_headlines() -> List[Dict]:
    if FINNHUB_KEY:
        try:
            r = requests.get(f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_KEY}")
            if r.status_code == 200:
                news = r.json()[:8]
                return [{"title": n["headline"], "link": n["url"]} for n in news if n.get("headline")]
        except Exception:
            pass
    # fallback 뉴스
    return [
        {"title": "미국 증시, 기술주 강세 지속", "link": "https://finance.yahoo.com"},
        {"title": "반도체 업황 회복 기대감", "link": "https://finance.yahoo.com"},
    ]

def get_market_snapshot() -> Dict:
    indices = {"SPY": "S&P500", "QQQ": "NASDAQ", "^KS11": "KOSPI"}
    result = {}
    for sym, name in indices.items():
        data = get_price(sym)
        result[name] = data or {"price": 0, "change_pct": 0}
    return result
