# backend/core/data_handler.py
import os
import time
import re
import requests
import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from xml.etree import ElementTree

# 환경변수 (Render 대시보드에서 설정)
FINNHUB_KEY = os.getenv("FINNHUB_KEY")
# ALPHA_VANTAGE_KEY, ALPHA_VANTAGE_KEY1~5 등 여러 키 중 사용 가능한 것 선택
ALPHA_KEYS = [
    v
    for name in ["ALPHA_VANTAGE_KEY"] + [f"ALPHA_VANTAGE_KEY{i}" for i in range(1, 6)]
    if (v := os.getenv(name))
]

# 단순 TTL 캐시 (가격 재호출 최소화)
PRICE_CACHE: Dict[str, Tuple[float, Optional[Dict]]] = {}

def _safe_float(val) -> Optional[float]:
    try:
        return float(val)
    except Exception:
        return None

def _normalize_percent(val: Optional[float]) -> Optional[float]:
    """
    yfinance는 배당/ROE 등을 소수(0.05)나 퍼센트(5)로 섞어서 반환할 때가 있어
    1.5보다 큰 값은 퍼센트로 간주해 100으로 나눠 정규화한다.
    """
    num = _safe_float(val)
    if num is None:
        return None
    return num / 100 if num > 1.5 else num

def _extract_price(info: Dict[str, Any]) -> Optional[float]:
    """펀더멘털 계산에 쓸 현재가를 info에서 최대한 추출."""
    for key in ["currentPrice", "regularMarketPrice", "previousClose"]:
        price = _safe_float(info.get(key))
        if price:
            return price
    return None

def _compute_dividend_yield(info: Dict[str, Any], price: Optional[float]) -> Optional[float]:
    """
    우선순위:
    1) dividendYield/trailingAnnualDividendYield (소수/퍼센트 모두 허용, 정규화)
    2) dividendRate(배당금)/current price 로 계산
    """
    direct = _normalize_percent(
        info.get("dividendYield") or info.get("trailingAnnualDividendYield")
    )
    if direct is not None:
        return direct

    rate = _safe_float(
        info.get("dividendRate") or info.get("trailingAnnualDividendRate")
    )
    if rate and price:
        return rate / price

    return None

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

def get_price(ticker: str, ttl: int = 90) -> Optional[Dict]:
    """Finnhub → Alpha Vantage → yfinance 순으로 시도, TTL 캐시 포함."""
    ticker_key = ticker.upper()
    now = time.time()

    # 캐시 히트 시 바로 반환
    cached = PRICE_CACHE.get(ticker_key)
    if cached:
        saved_time, saved_value = cached
        if now - saved_time < ttl:
            return saved_value

    result = finnhub_quote(ticker_key)
    if result:
        PRICE_CACHE[ticker_key] = (now, result)
        print(f"[Finnhub] {ticker_key}: {result['price']}")
        return result

    result = alpha_quote(ticker_key)
    if result:
        PRICE_CACHE[ticker_key] = (now, result)
        print(f"[Alpha] {ticker_key}: {result['price']}")
        return result

    result = yfinance_quote(ticker_key)
    if result:
        PRICE_CACHE[ticker_key] = (now, result)
        print(f"[yfinance] {ticker_key}: {result['price']}")
        return result

    print(f"[모든 소스 실패] {ticker_key}")
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
        price = _extract_price(info)
        return {
            "market_cap": info.get("marketCap"),
            "per": info.get("trailingPE") or info.get("forwardPE"),
            "pbr": info.get("priceToBook"),
            "roe": _normalize_percent(info.get("returnOnEquity")),
            "dividend_yield": _compute_dividend_yield(info, price),
            "psr": info.get("priceToSalesTrailing12Months") or info.get("priceToSalesTTM"),
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
    """
    뉴스는 yfinance → Finnhub(보유 시) → Yahoo search 순서로 시도 후, 빈 리스트 반환.
    """
    is_korea = ticker.endswith(".KS") or re.fullmatch(r"[0-9]{6}", ticker)
    search_key = ticker.replace(".KS", "") if is_korea else ticker
    if is_korea:
        try:
            r = requests.get(
                "https://news.google.com/rss/search",
                params={"q": search_key, "hl": "ko", "gl": "KR", "ceid": "KR:ko"},
                timeout=8,
            )
            if r.status_code == 200 and r.text:
                root = ElementTree.fromstring(r.text)
                items: List[Dict[str, Any]] = []
                for item in root.findall(".//item")[:limit]:
                    title = item.findtext("title")
                    link = item.findtext("link")
                    pub = item.findtext("source") or "Google News"
                    if title and link:
                        items.append(
                            {
                                "title": title,
                                "link": link,
                                "publisher": pub,
                                "published_at": item.findtext("pubDate"),
                            }
                        )
                if items:
                    return items
        except Exception:
            pass

    # 1) yfinance
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
        if items:
            return items
    except Exception:
        pass

    # 2) Finnhub (보유 키가 있는 경우)
    if FINNHUB_KEY:
        try:
            today = datetime.utcnow().date()
            start = today - timedelta(days=30)
            url = (
                "https://finnhub.io/api/v1/company-news"
                f"?symbol={ticker}&from={start}&to={today}&token={FINNHUB_KEY}"
            )
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json() or []
                items: List[Dict[str, Any]] = []
                for n in data[:limit]:
                    headline = n.get("headline")
                    if not headline or not n.get("url"):
                        continue
                    items.append(
                        {
                            "title": headline,
                            "link": n["url"],
                            "publisher": n.get("source"),
                            "published_at": n.get("datetime"),
                        }
                    )
                if items:
                    return items
        except Exception:
            pass

    # 3) Yahoo search API (무인증)
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v1/finance/search",
            params={"q": search_key, "quotesCount": 0, "newsCount": limit},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        if r.status_code == 200:
            data = r.json() or {}
            items: List[Dict[str, Any]] = []
            for n in data.get("news", [])[:limit]:
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
            if items:
                return items
    except Exception:
        pass

    # 4) 최소 fallback: 종목 뉴스 페이지 링크라도 제공 (KR 종목은 네이버/구글 링크 포함)
    fallback_links = [
        {
            "title": f"{ticker} 최신 뉴스 모아보기",
            "link": f"https://finance.yahoo.com/quote/{ticker}/news",
            "publisher": "Yahoo Finance",
            "published_at": None,
        },
        {
            "title": f"{search_key} 검색 결과 (Google News)",
            "link": f"https://news.google.com/search?q={search_key}",
            "publisher": "Google News",
            "published_at": None,
        },
    ]

    if is_korea:
        fallback_links.insert(
            0,
            {
                "title": f"{search_key} 네이버 금융 뉴스",
                "link": f"https://finance.naver.com/item/news_news.naver?code={search_key}",
                "publisher": "Naver Finance",
                "published_at": None,
            },
        )
    return fallback_links

def get_global_headlines(lang: str = "en") -> List[Dict]:
    lang = (lang or "en").lower()
    # 0) Korean 우선 처리: 구글 뉴스 RSS (무인증)
    if lang == "ko":
        try:
            r = requests.get("https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko", timeout=8)
            if r.status_code == 200 and r.text:
                root = ElementTree.fromstring(r.text)
                items = []
                for item in root.findall(".//item")[:8]:
                    title = item.findtext("title")
                    link = item.findtext("link")
                    if title and link:
                        items.append({"title": title, "link": link, "publisher": "Google News"})
                if items:
                    return items
        except Exception:
            pass

    if FINNHUB_KEY:
        try:
            r = requests.get(f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_KEY}")
            if r.status_code == 200:
                news = r.json()[:8]
                return [{"title": n["headline"], "link": n["url"], "publisher": n.get("source")} for n in news if n.get("headline")]
        except Exception:
            pass
    # fallback 뉴스 (언어별)
    if lang == "ko":
        return [
            {"title": "미국 기술주 강세, 나스닥 상승 마감", "link": "https://finance.naver.com/news/"},
            {"title": "반도체 업황 회복 기대감 확대", "link": "https://finance.naver.com/news/"},
            {"title": "연준 금리 동결 기조 유지 전망", "link": "https://finance.naver.com/news/"},
        ]
    return [
        {"title": "U.S. tech leads gains as Nasdaq closes higher", "link": "https://finance.yahoo.com"},
        {"title": "Chip recovery optimism grows among investors", "link": "https://finance.yahoo.com"},
        {"title": "Fed seen holding rates steady amid soft inflation", "link": "https://finance.yahoo.com"},
    ]

def get_market_snapshot() -> Dict:
    indices = {"SPY": "S&P500", "QQQ": "NASDAQ", "^KS11": "KOSPI"}
    result = {}
    for sym, name in indices.items():
        data = get_price(sym)
        result[name] = data or {"price": 0, "change_pct": 0}
    return result
