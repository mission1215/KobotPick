# kobotPick/backEnd/core/kobot_engine.py (로직은 이전에 제공된 내용과 동일)

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from .data_handler import (
    get_historical_data,
    get_stock_info,
    get_news_items,
    FINNHUB_KEY,
    ALPHA_KEYS,
)
from .utils import calculate_technical_indicators

# 이전에 제공된 analyze_and_recommend 함수 코드를 여기에 배치합니다.

NO_REMOTE_DATA = not FINNHUB_KEY and not ALPHA_KEYS

def analyze_and_recommend(ticker: str, allow_partial: bool = False, country_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if NO_REMOTE_DATA:
        # 외부 데이터 소스가 모두 없을 때는 최소한의 더미 리포트를 즉시 반환해 API 지연을 막는다.
        now_iso = datetime.now(timezone.utc).isoformat()
        country, currency = detect_region_currency(ticker, None)
        price_val = 0.0
        return {
            'ticker': ticker,
            'name': ticker,
            'current_price': price_val,
            'last_updated': now_iso,
            'country': country,
            'currency': currency,
            'fundamentals': {
                'market_cap': None,
                'per': None,
                'pbr': None,
                'roe': None,
                'dividend_yield': None,
                'psr': None,
            },
            'recommendation': {
                'action': 'HOLD',
                'buy_price': price_val,
                'sell_price': price_val,
                'stop_loss': price_val,
                'rationale': '데이터 소스가 연결되지 않아 임시 정보를 표시합니다.',
            },
            'historical': [],
            'news': [],
            'profile': {
                'sector': None,
                'industry': None,
                'website': None,
                'summary': None,
                'employees': None,
                'exchange': None,
                'currency': currency,
            }
        }
    # 캐시 체크
    now = time.time()
    cached = REC_CACHE.get(ticker)
    if cached and (now - cached["ts"] < REC_CACHE_TTL_SECONDS):
        return cached["data"]

    # 1. 데이터 수집 (data_handler 사용)
    hist = get_historical_data(ticker)
    info = get_stock_info(ticker)

    if hist is None or not info.get('current_price'):
        fallback_price = info.get('regular_market_price') or info.get('previous_close')
        if not allow_partial or fallback_price is None:
            return None

        country, currency = detect_region_currency(ticker, info.get('currency') or (country_hint if country_hint else None))
        news_lang = "ko" if country == "KR" else "en"
        price_val = float(fallback_price)
        result = {
            'ticker': ticker,
            'name': info.get('name', ticker),
            'current_price': round(price_val, 2),
            'last_updated': datetime.now(timezone.utc).isoformat(),
            'country': country,
            'currency': currency,
            'fundamentals': {
                'market_cap': info.get('market_cap'),
                'per': info.get('per'),
                'pbr': info.get('pbr'),
                'roe': info.get('roe'),
                'dividend_yield': info.get('dividend_yield'),
                'psr': info.get('psr'),
            },
            'recommendation': {
                'action': 'HOLD',
                'buy_price': round(price_val, 2),
                'sell_price': round(price_val, 2),
                'stop_loss': round(price_val * 0.98, 2),
                'rationale': '데이터가 제한적입니다. 기본 정보만 제공합니다.'
            },
            'historical': [],
            'news': get_news_items(ticker, lang=news_lang),
            'profile': {
                'sector': info.get('sector'),
                'industry': info.get('industry'),
                'website': info.get('website'),
                'summary': info.get('summary'),
                'employees': info.get('employees'),
                'exchange': info.get('exchange'),
                'currency': currency,
            }
        }
        REC_CACHE[ticker] = {"ts": now, "data": result}
        return result

    # 2. 지표 계산 (utils 사용)
    df = calculate_technical_indicators(hist)
    latest = df.iloc[-1]

    current_price = info['current_price']
    stock_name = info['name']

    # 3. 가격 산출 로직 적용 (V2 로직)
    # ... (생략: 이전에 제공된 로직을 그대로 여기에 넣습니다.)

    bb_lower = latest.get('BBL_20_2', current_price * 0.95)
    bb_upper = latest.get('BBU_20_2', current_price * 1.05)
    rsi_val = latest.get('RSI_14', 50)
    ma_20 = latest.get('BBM_20_2', current_price)

    buy_target = max(current_price * 0.98, bb_lower)
    sell_target = max(bb_upper, current_price * 1.07)
    stop_loss = ma_20 * 0.99

    if rsi_val < 35:
        action = 'STRONG_BUY'
        rationale = "RSI가 과매도(35 이하) 영역에 있으며, 강력한 매수 시점입니다. 볼린저 밴드 하단이 지지선 역할을 합니다."
    elif rsi_val < 70 and current_price < ma_20:
        action = 'BUY'
        rationale = "현재 가격은 20일 이동평균선 아래에 있으나, RSI는 과열되지 않았습니다. 매수가에서 반등을 기대합니다."
    else:
        action = 'HOLD'
        rationale = "RSI가 높아져 단기적인 과열 가능성이 있습니다. 관망 후 추후 매수 시점을 노려보세요."

    # 4. 최종 결과 반환
    # 히스토리 직렬화 (최근 90일)
    hist_serialized = []
    hist_reset = hist.reset_index()
    for _, row in hist_reset.tail(90).iterrows():
        # Date가 Timestamp일 경우 ISO 문자열로 변환
        date_val = row['Date'].isoformat() if hasattr(row['Date'], 'isoformat') else str(row['Date'])
        hist_serialized.append({
            'date': date_val,
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close']),
        })

    country, currency = detect_region_currency(ticker, info.get('currency'))
    news_lang = "ko" if country == "KR" else "en"

    result = {
        'ticker': ticker,
        'name': stock_name,
        'current_price': round(current_price, 2),
        'last_updated': datetime.now(timezone.utc).isoformat(),
        'country': country,
        'currency': currency,
        'fundamentals': {
            'market_cap': info.get('market_cap'),
            'per': info.get('per'),
            'pbr': info.get('pbr'),
            'roe': info.get('roe'),
            'dividend_yield': info.get('dividend_yield'),
            'psr': info.get('psr'),
        },
        'recommendation': {
            'action': action,
            'buy_price': round(buy_target, 2),
            'sell_price': round(sell_target, 2),
            'stop_loss': round(stop_loss, 2),
            'rationale': rationale
        },
        'historical': hist_serialized,
        'news': get_news_items(ticker, lang=news_lang),
        'profile': {
            'sector': info.get('sector'),
            'industry': info.get('industry'),
            'website': info.get('website'),
            'summary': info.get('summary'),
            'employees': info.get('employees'),
            'exchange': info.get('exchange'),
            'currency': currency,
        }
    }
    REC_CACHE[ticker] = {"ts": now, "data": result}
    return result

def compute_score(latest_row: Any, info: Dict[str, Any]) -> int:
    """간단한 스코어링: 모멘텀/RSI/밸류 지표 조합."""
    score = 50

    close = latest_row.get('Close')
    sma20 = latest_row.get('SMA_20') or latest_row.get('BBM_20_2')
    sma60 = latest_row.get('SMA_60')
    rsi = latest_row.get('RSI_14')

    if close and sma20:
        if close > sma20:
            score += 10
        if sma60 and close > sma60:
            score += 5
    if rsi:
        if 40 <= rsi <= 60:
            score += 8
        elif rsi < 35:
            score += 6
        elif rsi > 70:
            score -= 6

    per = info.get('per')
    pbr = info.get('pbr')
    roe = info.get('roe')
    div_yield = info.get('dividend_yield')
    psr = info.get('psr')

    if per and per < 25:
        score += 3
    if pbr and pbr < 5:
        score += 2
    if roe and roe > 0.1:
        score += 3
    if div_yield and div_yield > 0.01:
        score += 2
    if psr and psr < 10:
        score += 2

    return int(max(0, min(100, score)))


def get_top_stocks() -> List[Dict[str, str]]:
    """해외 5, 국내 5, ETF 5 종목을 실데이터 기반으로 스코어링해 반환."""
    if NO_REMOTE_DATA:
        # 데이터 소스가 없으면 빠른 응답을 위해 기본 리스트만 돌려준다.
        fallback = [
            {"ticker": "AAPL", "name": "Apple Inc.", "country": "US", "score": 50},
            {"ticker": "TSLA", "name": "Tesla, Inc.", "country": "US", "score": 50},
            {"ticker": "NVDA", "name": "NVIDIA Corp.", "country": "US", "score": 50},
            {"ticker": "MSFT", "name": "Microsoft Corp.", "country": "US", "score": 50},
            {"ticker": "AMZN", "name": "Amazon.com, Inc.", "country": "US", "score": 50},
            {"ticker": "005930.KS", "name": "Samsung Electronics", "country": "KR", "score": 50},
            {"ticker": "000660.KS", "name": "SK hynix", "country": "KR", "score": 50},
            {"ticker": "035420.KS", "name": "NAVER Corp.", "country": "KR", "score": 50},
            {"ticker": "051910.KS", "name": "LG Chem", "country": "KR", "score": 50},
            {"ticker": "207940.KS", "name": "Samsung Biologics", "country": "KR", "score": 50},
            {"ticker": "SPY", "name": "SPDR S&P 500 ETF", "country": "ETF", "score": 50},
            {"ticker": "QQQ", "name": "Invesco QQQ Trust", "country": "ETF", "score": 50},
            {"ticker": "VTI", "name": "Vanguard Total Stock Market ETF", "country": "ETF", "score": 50},
            {"ticker": "IWM", "name": "iShares Russell 2000 ETF", "country": "ETF", "score": 50},
            {"ticker": "ARKK", "name": "ARK Innovation ETF", "country": "ETF", "score": 50},
        ]
        PICKS_CACHE["data"] = fallback
        PICKS_CACHE["ts"] = time.time()
        return fallback
    now = time.time()
    if PICKS_CACHE["data"] and (now - PICKS_CACHE["ts"] < PICKS_CACHE_TTL_SECONDS):
        return PICKS_CACHE["data"]
    candidates = [
        {"ticker": "AAPL", "name": "Apple Inc.", "country": "US"},
        {"ticker": "TSLA", "name": "Tesla, Inc.", "country": "US"},
        {"ticker": "NVDA", "name": "NVIDIA Corp.", "country": "US"},
        {"ticker": "MSFT", "name": "Microsoft Corp.", "country": "US"},
        {"ticker": "AMZN", "name": "Amazon.com, Inc.", "country": "US"},
        {"ticker": "005930.KS", "name": "Samsung Electronics", "country": "KR"},
        {"ticker": "000660.KS", "name": "SK hynix", "country": "KR"},
        {"ticker": "035420.KS", "name": "NAVER Corp.", "country": "KR"},
        {"ticker": "051910.KS", "name": "LG Chem", "country": "KR"},
        {"ticker": "207940.KS", "name": "Samsung Biologics", "country": "KR"},
        # ETF (USD)
        {"ticker": "SPY", "name": "SPDR S&P 500 ETF", "country": "ETF"},
        {"ticker": "QQQ", "name": "Invesco QQQ Trust", "country": "ETF"},
        {"ticker": "VTI", "name": "Vanguard Total Stock Market ETF", "country": "ETF"},
        {"ticker": "IWM", "name": "iShares Russell 2000 ETF", "country": "ETF"},
        {"ticker": "ARKK", "name": "ARK Innovation ETF", "country": "ETF"},
    ]

    results = []
    for item in candidates:
        ticker = item["ticker"]
        try:
            hist = get_historical_data(ticker, period="3mo")
            info = get_stock_info(ticker)
            if hist is None or info.get('current_price') is None:
                raise ValueError("data missing")

            df = calculate_technical_indicators(hist.copy())
            latest = df.iloc[-1]
            score = compute_score(latest, info)
            results.append({
                **item,
                "score": score
            })
        except Exception as e:
            print(f"Score error for {ticker}: {e}")
            results.append({**item, "score": 50})

    # 상위 5개씩
    us_sorted = sorted([r for r in results if r["country"] == "US"], key=lambda x: x["score"], reverse=True)[:5]
    kr_sorted = sorted([r for r in results if r["country"] == "KR"], key=lambda x: x["score"], reverse=True)[:5]
    etf_sorted = sorted([r for r in results if r["country"] == "ETF"], key=lambda x: x["score"], reverse=True)[:5]
    result = us_sorted + kr_sorted + etf_sorted
    PICKS_CACHE["data"] = result
    PICKS_CACHE["ts"] = now
    return result


def get_picks_with_recommendations() -> List[Dict[str, Any]]:
    """picks + recommendation을 한번에 반환 (병렬 처리, 캐시 활용)."""
    picks = get_top_stocks()
    if NO_REMOTE_DATA:
        # 데이터 소스가 없을 때는 빠르게 더미 rec를 붙여 반환
        now_iso = datetime.now(timezone.utc).isoformat()
        results = []
        for p in picks:
            country, currency = detect_region_currency(p["ticker"], None)
            rec = {
                "ticker": p["ticker"],
                "name": p["name"],
                "current_price": 0.0,
                "last_updated": now_iso,
                "country": country,
                "currency": currency,
                "fundamentals": {},
                "recommendation": {
                    "action": "HOLD",
                    "buy_price": 0.0,
                    "sell_price": 0.0,
                    "stop_loss": 0.0,
                    "rationale": "데이터 소스가 연결되지 않아 임시 정보를 표시합니다.",
                },
                "historical": [],
                "news": [],
                "profile": {},
            }
            results.append({**p, "rec": rec})
        return results
    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_map = {executor.submit(analyze_and_recommend, p["ticker"], True, p.get("country")): p for p in picks}
        for fut in as_completed(future_map):
            base = future_map[fut]
            try:
                rec = fut.result()
                if rec:
                    results.append({**base, "rec": rec})
            except Exception as e:
                print(f"full picks error {base['ticker']}: {e}")
    # 순서를 원래 picks 순서대로 정렬
    pick_order = {p["ticker"]: idx for idx, p in enumerate(picks)}
    results.sort(key=lambda x: pick_order.get(x["ticker"], 999))
    return results


def detect_region_currency(ticker: str, raw_currency: Optional[str]) -> (str, str):
    ticker_upper = ticker.upper()
    if ticker_upper.endswith(".KS") or ticker_upper.endswith(".KQ"):
        return "KR", "KRW"
    if raw_currency:
        return "US", raw_currency
    return "US", "USD"


# 단순 인메모리 캐시
REC_CACHE: Dict[str, Dict[str, Any]] = {}
PICKS_CACHE = {"ts": 0.0, "data": None}
REC_CACHE_TTL_SECONDS = 300  # 5분
PICKS_CACHE_TTL_SECONDS = 300  # 5분

# --- 이전 main.py에 있던 함수 구조를 제거하고, 실제 main.py에서 이 함수들을 호출하도록 합니다.
