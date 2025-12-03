# backend/core/data_handler.py

import os
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
# ... (기존 import 생략)

# 재시도 세션 만들기 (Yahoo가 자주 429 주니까)
session = requests.Session()
retry = Retry(total=4, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)

def yahoo_quote(symbol: str) -> Optional[dict]:
    try:
        r = session.get(
            "https://query1.finance.yahoo.com/v7/finance/quote",
            params={"symbols": symbol},
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
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
        print(f"[Yahoo Quote 실패] {symbol}: {e}")  # Render 로그에서 확인 가능
        return None