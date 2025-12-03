# backend/core/data_handler.py
import os
import time
import requests
import yfinance as yf
from typing import Optional, Dict, Any, List
from datetime import datetime

# 환경변수 (Render 대시보드에서 설정)
FINNHUB_KEY = os.getenv("FINNHUB_KEY")
ALPHA_KEY = os.getenv("ALPHA_VANTAGE_KEY")  # 하나만 있어도 됨

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
                    "source": "finnhub"
                }
    except:
        pass
    return None

def alpha_quote(ticker: str) -> Optional[Dict]:
    if not ALPHA_KEY:
        return None
    try:
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": ticker,
            "apikey": ALPHA_KEY
        }
        r = requests.get(url, params=params, timeout=12)
        data = r.json().get("Global Quote", {})
        if data.get("05. price"):
            price = float(data["05. price"])
            change_pct = float(data.get("10. change percent", "0").replace("%", ""))
            return {
                "price": price,
                "prev": price / (1 + change_pct/100) if change_pct != 0 else price,
                "change_pct": round(change_pct, 2),
                "source": "alpha"
            }
    except:
        pass
    return None

def yfinance_quote(ticker: str) -> Optional[Dict]:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="2d")
        if len(hist) < 2:
            return None
        current = hist["Close"].iloc[-1]
        prev = hist["Close"].iloc[-2]
        return {
            "price": round(current, 2),
            "prev": round(prev, 2),
            "change_pct": round(((current - prev) / prev) * 100, 2),
            "name": info.get("longName") or info.get("shortName") or ticker,
            "source": "yfinance"
        }
    except:
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

def get_global_headlines() -> List[Dict]:
    if FINNHUB_KEY:
        try:
            r = requests.get(f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_KEY}")
            if r.status_code == 200:
                news = r.json()[:8]
                return [{"title": n["headline"], "link": n["url"]} for n in news if n.get("headline")]
        except:
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