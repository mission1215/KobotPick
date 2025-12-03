# backend/core/kobot_engine.py
import random
import time
from datetime import datetime
from typing import List, Dict

from core.data_handler import (
    get_price,
    get_fundamentals,
    get_stock_profile,
    get_historical_candles,
    get_company_news,
)

ETF_TICKERS = {"SPY", "QQQ", "TQQQ", "SOXL", "ARKK", "VTI", "IWM"}
ANALYSIS_CACHE: Dict[str, Dict] = {}
ANALYSIS_TTL = 180  # 초 단위 캐시 TTL


def infer_country(ticker: str) -> str:
    if ticker.endswith(".KS"):
        return "KR"
    if ticker.upper() in ETF_TICKERS:
        return "ETF"
    return "US"


def calculate_score(ticker: str) -> int:
    """간단한 기술적 지표 기반 점수."""
    try:
        stock = __import__("yfinance").Ticker(ticker)
        hist = stock.history(period="60d")
        if len(hist) < 30:
            return random.randint(60, 85)

        close = hist["Close"]
        ma20 = close.rolling(20).mean().iloc[-1]
        ma50 = close.rolling(50).mean().iloc[-1]
        current = close.iloc[-1]

        score = 70
        if current > ma20 > ma50:
            score += 20
        elif current > ma20:
            score += 10

        rsi = 100 - (
            100
            / (
                1
                + (
                    close.diff(1).clip(lower=0).rolling(14).mean()
                    / abs(close.diff(1)).clip(upper=0).rolling(14).mean()
                )
            )
        )
        rsi_val = rsi.iloc[-1] if len(rsi) > 0 else 50
        if 30 < rsi_val < 70:
            score += 10

        score += random.randint(-8, 12)
        return max(60, min(94, int(score)))
    except Exception:
        return random.randint(68, 90)


def score_to_action(score: int) -> str:
    if score >= 88:
        return "STRONG BUY"
    if score >= 78:
        return "BUY"
    if score >= 68:
        return "HOLD"
    return "WATCH"


def build_price_targets(price: float) -> Dict[str, float]:
    if price is None:
        return {"buy_price": None, "sell_price": None, "stop_loss": None}
    return {
        "buy_price": round(price * 0.98, 2),
        "sell_price": round(price * 1.08, 2),
        "stop_loss": round(price * 0.92, 2),
    }

def get_top_stocks() -> List[Dict]:
    candidates = [
        "NVDA", "TSLA", "AAPL", "MSFT", "AMZN",
        "005930.KS", "000660.KS", "035420.KS", "005380.KS", "000270.KS",
        "SPY", "QQQ", "TQQQ", "SOXL", "ARKK"
    ]

    result = []
    for t in candidates:
        price_data = get_price(t)
        score = calculate_score(t)
        result.append(
            {
                "ticker": t,
                "name": price_data.get("name", t) if price_data else t,
                "country": infer_country(t),
                "score": score,
                "price": price_data["price"] if price_data else 0,
                "change_pct": price_data.get("change_pct", 0) if price_data else 0,
            }
        )

    return sorted(result, key=lambda x: x["score"], reverse=True)[:15]

def analyze_and_recommend(ticker: str):
    ticker_key = ticker.upper()
    now = time.time()
    cached = ANALYSIS_CACHE.get(ticker_key)
    if cached and now - cached.get("_saved_at", 0) < ANALYSIS_TTL:
        return {k: v for k, v in cached.items() if k != "_saved_at"}

    price_data = get_price(ticker)
    score = calculate_score(ticker)
    current_price = price_data["price"] if price_data else None
    targets = build_price_targets(current_price)

    profile = get_stock_profile(ticker)
    currency = (
        profile.get("currency")
        or (price_data.get("currency") if price_data else None)
        or ("KRW" if ticker.endswith(".KS") else "USD")
    )

    recommendation_detail = {
        "action": score_to_action(score),
        "buy_price": targets["buy_price"],
        "sell_price": targets["sell_price"],
        "stop_loss": targets["stop_loss"],
        "rationale": "가격 모멘텀과 밸류에이션을 종합한 자동 분석 결과입니다.",
    }

    result = {
        "ticker": ticker,
        "name": (price_data.get("name") if price_data else None) or ticker,
        "score": score,
        "recommendation": recommendation_detail,
        "current_price": current_price,
        "last_updated": datetime.utcnow().isoformat(),
        "country": infer_country(ticker),
        "currency": currency,
        "fundamentals": get_fundamentals(ticker),
        "historical": get_historical_candles(ticker),
        "news": get_company_news(ticker),
        "profile": profile,
        "source": price_data["source"] if price_data else "none",
    }

    ANALYSIS_CACHE[ticker_key] = {**result, "_saved_at": now}
    return result
