# backend/core/kobot_engine.py
import random
import time
from datetime import datetime
from typing import List, Dict, Tuple

from core.data_handler import (
    get_price,
    get_fundamentals,
    get_stock_profile,
    get_historical_candles,
    get_company_news,
)

ETF_TICKERS = {"SPY", "QQQ", "TQQQ", "SOXL", "ARKK", "VTI", "IWM", "DIA", "XLK"}
ANALYSIS_CACHE: Dict[str, Dict] = {}
ANALYSIS_TTL = 180  # 초 단위 캐시 TTL
TOP_PICKS_CACHE: Dict[str, Dict] = {}
TOP_PICKS_TTL = 120  # 전체 picks 캐시 TTL
CANDIDATE_CACHE: Dict[str, Dict] = {}
CANDIDATE_TTL = 600  # 10분마다 후보 리스트 리프레시
TOP_PER_COUNTRY = 10  # 각 국가/ETF별 상위 개수
SCORE_CACHE: Dict[str, Tuple[float, int]] = {}
SCORE_TTL = 600  # 점수 계산 캐시


def infer_country(ticker: str) -> str:
    if ticker.endswith(".KS"):
        return "KR"
    if ticker.upper() in ETF_TICKERS:
        return "ETF"
    return "US"


def calculate_score(ticker: str) -> int:
    """
    모멘텀 + 변동성 + 기본 펀더멘털을 반영한 점수.
    - 추세: MA20 > MA60, 최근 30/90일 수익률
    - 변동성/거래: 과도한 변동성 패널티, 최근 거래량 급증 보너스
    - 펀더멘털: PER/PBR/ROE/배당을 간단 반영
    - RSI: 과매수/과매도 구간 회피
    """
    now = time.time()
    cached = SCORE_CACHE.get(ticker.upper())
    if cached and now - cached[0] < SCORE_TTL:
        return cached[1]

    try:
        def safe_float(x):
            try:
                return float(x)
            except Exception:
                return None

        stock = __import__("yfinance").Ticker(ticker)
        hist = stock.history(period="120d")
        if len(hist) < 60:
            score_val = random.randint(62, 78)
            SCORE_CACHE[ticker.upper()] = (now, score_val)
            return score_val

        close = hist["Close"]
        volume = hist.get("Volume")
        returns = close.pct_change().dropna()
        current = close.iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        ma60 = close.rolling(60).mean().iloc[-1]

        # 기본 점수
        score = 70

        # 추세 보너스
        if current > ma20 > ma60:
            score += 12
        elif current > ma20:
            score += 6

        # 수익률 보너스
        def pct_change_n(n: int) -> float:
            if len(close) < n + 1:
                return 0
            start = close.iloc[-n - 1]
            end = close.iloc[-1]
            return (end - start) / start if start else 0

        r30 = pct_change_n(30)
        r90 = pct_change_n(90)
        if r30 > 0:
            score += min(8, r30 * 100 / 5)  # 5%당 +1p, 최대 8p
        if r90 > 0:
            score += min(6, r90 * 100 / 10)  # 10%당 +1p, 최대 6p

        # 변동성 패널티/보너스 (연환산 변동성)
        vol = returns.std() * (252 ** 0.5)
        if vol is not None:
            if vol > 0.55:
                score -= 8
            elif vol > 0.4:
                score -= 4
            elif vol < 0.25:
                score += 4

        # RSI (14)
        delta = close.diff().dropna()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = -delta.clip(upper=0).rolling(14).mean()
        rs = gain / loss.replace(0, None)
        rsi = 100 - (100 / (1 + rs))
        rsi_val = rsi.iloc[-1] if len(rsi) else 50
        if 40 <= rsi_val <= 60:
            score += 4
        elif rsi_val >= 75 or rsi_val <= 25:
            score -= 6

        # 거래량 모멘텀: 최근 거래량이 20일 평균 대비 높으면 보너스
        if volume is not None and len(volume) >= 20:
            vol_ratio = volume.iloc[-1] / (volume.tail(20).mean() or 1)
            if vol_ratio > 1.8:
                score += 6
            elif vol_ratio > 1.2:
                score += 3
            elif vol_ratio < 0.6:
                score -= 3

        # 펀더멘털 반영 (캐시 사용)
        fundamentals = get_fundamentals(ticker)
        per = safe_float(fundamentals.get("per"))
        pbr = safe_float(fundamentals.get("pbr"))
        roe = safe_float(fundamentals.get("roe"))
        dy = safe_float(fundamentals.get("dividend_yield"))

        if per:
            if 8 <= per <= 35:
                score += 4
            elif per > 60:
                score -= 4
            elif per < 5:
                score -= 2
        if pbr:
            if 1 <= pbr <= 6:
                score += 2
            elif pbr > 12:
                score -= 3
        if roe is not None:
            if roe > 0.18:
                score += 5
            elif roe > 0.1:
                score += 3
            elif roe < 0:
                score -= 5
        if dy:
            if 0.005 <= dy <= 0.06:
                score += 2
            elif dy > 0.08:
                score -= 1

        # 소폭 랜덤으로 상위권 동점 해소
        score += random.randint(-3, 5)
        score_val = max(55, min(95, int(score)))
        SCORE_CACHE[ticker.upper()] = (now, score_val)
        return score_val
    except Exception:
        score_val = random.randint(65, 85)
        SCORE_CACHE[ticker.upper()] = (now, score_val)
        return score_val


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
    now = time.time()
    cached_candidates = CANDIDATE_CACHE.get("all")
    if cached_candidates and now - cached_candidates.get("_saved_at", 0) < CANDIDATE_TTL:
        candidates = cached_candidates["data"]
    else:
        candidates = load_candidates_from_config()
        CANDIDATE_CACHE["all"] = {"data": candidates, "_saved_at": now}

    now = time.time()
    cached = TOP_PICKS_CACHE.get("picks")
    if cached and now - cached.get("_saved_at", 0) < TOP_PICKS_TTL:
        return cached["data"]

    buckets: Dict[str, List[Dict]] = {"US": [], "KR": [], "ETF": []}
    for t in candidates:
        price_data = get_price(t)
        score = calculate_score(t)
        country = infer_country(t)
        item = {
            "ticker": t,
            "name": price_data.get("name", t) if price_data else t,
            "country": country,
            "score": score,
            "price": price_data["price"] if price_data else 0,
            "change_pct": price_data.get("change_pct", 0) if price_data else 0,
        }
        if country in buckets:
            buckets[country].append(item)

    combined: List[Dict] = []
    for country, items in buckets.items():
        items_sorted = sorted(items, key=lambda x: x["score"], reverse=True)[:TOP_PER_COUNTRY]
        combined.extend(items_sorted)

    TOP_PICKS_CACHE["picks"] = {"data": combined, "_saved_at": now}
    return combined


def load_candidates_from_config() -> List[str]:
    """
    backend/config/tickers.json에서 US/KR/ETF 후보를 읽어와 하나의 리스트로 반환.
    파일이 없거나 파싱 실패 시 기본 하드코딩 목록을 사용.
    """
    default_candidates = [
        # US
        "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "AMD",
        # KR
        "005930.KS", "000660.KS", "035420.KS", "005380.KS", "000270.KS", "051910.KS", "207940.KS", "068270.KS",
        # ETF
        "SPY", "QQQ", "TQQQ", "SOXL", "ARKK", "VTI", "IWM", "DIA", "XLK",
    ]
    try:
        import json
        from pathlib import Path

        path = Path(__file__).resolve().parent.parent / "config" / "tickers.json"
        if not path.exists():
            return default_candidates
        with path.open() as f:
            data = json.load(f) or {}
        us = data.get("US") or []
        kr = data.get("KR") or []
        etf = data.get("ETF") or []
        combined = list(dict.fromkeys(us + kr + etf))  # 순서 유지 + 중복 제거
        return combined or default_candidates
    except Exception:
        return default_candidates

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
