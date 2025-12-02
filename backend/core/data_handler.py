# kobotPick/backEnd/core/data_handler.py

import yfinance as yf
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, List
from urllib.parse import quote_plus

def get_historical_data(ticker: str, period: str = "3mo") -> Optional[pd.DataFrame]:
    """yfinance를 사용하여 종목의 과거 시세 데이터를 가져옵니다."""
    try:
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(period=period)
        if hist.empty:
            return None
        return hist
    except Exception as e:
        print(f"Error fetching historical data for {ticker}: {e}")
        return None

def get_stock_info(ticker: str) -> Dict[str, Any]:
    """yfinance를 사용하여 종목의 기본 정보를 가져옵니다."""
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        # 필요한 정보만 추출하거나, 전체 정보를 반환
        return {
            'name': info.get('shortName', ticker),
            'current_price': info.get('currentPrice'),
            'regular_market_price': info.get('regularMarketPrice'),
            'previous_close': info.get('previousClose'),
            'market_cap': info.get('marketCap'),
            'per': info.get('trailingPE'),
            'pbr': info.get('priceToBook'),
            'roe': info.get('returnOnEquity'),
            'dividend_yield': info.get('dividendYield'),
            'psr': info.get('priceToSalesTrailing12Months'),
            'currency': info.get('currency'),
            'exchange': info.get('exchange'),
            'sector': info.get('sector'),
            'industry': info.get('industry'),
            'website': info.get('website'),
            'summary': info.get('longBusinessSummary'),
            'employees': info.get('fullTimeEmployees'),
        }
    except Exception as e:
        print(f"Error fetching stock info for {ticker}: {e}")
        return {'name': ticker, 'current_price': None}


def get_news_items(ticker: str, limit: int = 6, lang: str = "en") -> List[Dict[str, Any]]:
    """
    yfinance 뉴스에 실패/부족하면 Google News RSS로 보완.
    lang: en/ko/ja/zh 등 Google News hl 파라미터에 사용.
    """
    items: List[Dict[str, Any]] = []
    try:
        news = yf.Ticker(ticker).news or []
        for n in news[:limit]:
            title = n.get("title")
            link = n.get("link")
            if not title or not link:
                continue
            items.append({
                "title": title,
                "link": link,
                "publisher": n.get("publisher"),
                "published_at": n.get("providerPublishTime")
            })
    except Exception as e:
        print(f"Error fetching news for {ticker}: {e}")

    # 보완: Google News RSS (무료, 키 없음)
    if len(items) < limit:
        try:
            query = quote_plus(ticker)
            # Google News 지역/언어 파라미터: hl=언어, gl=국가
            lang = lang or "en"
            region = "KR" if lang.startswith("ko") else "US"
            url = f"https://news.google.com/rss/search?q={query}&hl={lang}&gl={region}"
            resp = requests.get(url, timeout=5)
            if resp.ok:
                root = ET.fromstring(resp.content)
                channel = root.find('channel')
                if channel is not None:
                    for item in channel.findall('item'):
                        title_el = item.find('title')
                        link_el = item.find('link')
                        pub_el = item.find('pubDate')
                        title = title_el.text if title_el is not None else None
                        link = link_el.text if link_el is not None else None
                        if not title or not link:
                            continue
                        items.append({
                            "title": title,
                            "link": link,
                            "publisher": "Google News",
                            "published_at": pub_el.text if pub_el is not None else None
                        })
                        if len(items) >= limit:
                            break
        except Exception as e:
            print(f"Error fetching Google News RSS for {ticker}: {e}")

    return items[:limit]


def _calc_change(ticker: str) -> Optional[Dict[str, Any]]:
    """최근 2일 종가로 등락 계산."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d")
        if hist is None or hist.empty or len(hist["Close"]) < 2:
            return None
        last = hist["Close"].iloc[-1]
        prev = hist["Close"].iloc[-2]
        change = last - prev
        pct = (change / prev) * 100 if prev else 0
        return {"price": float(last), "change": float(change), "change_pct": float(pct)}
    except Exception as e:
        print(f"Error calc change for {ticker}: {e}")
        return None


def get_market_snapshot() -> Dict[str, Any]:
    """주요 지수/환율 요약."""
    tickers = {
        "SPX": "^GSPC",
        "NASDAQ": "^IXIC",
        "KOSPI": "^KS11",
        "USDKRW": "KRW=X",
    }
    result = {}
    for name, tk in tickers.items():
        data = _calc_change(tk)
        if data:
            result[name] = data
    return result


def get_global_headlines(limit: int = 6) -> List[Dict[str, Any]]:
    """시장 전반 뉴스 헤드라인 (Google News RSS)."""
    items: List[Dict[str, Any]] = []
    try:
        query = quote_plus("stock market finance")
        url = f"https://news.google.com/rss/search?q={query}"
        resp = requests.get(url, timeout=5)
        if resp.ok:
            root = ET.fromstring(resp.content)
            channel = root.find('channel')
            if channel is not None:
                for item in channel.findall('item')[:limit]:
                    title_el = item.find('title')
                    link_el = item.find('link')
                    pub_el = item.find('pubDate')
                    title = title_el.text if title_el is not None else None
                    link = link_el.text if link_el is not None else None
                    if not title or not link:
                        continue
                    items.append({
                        "title": title,
                        "link": link,
                        "publisher": "Google News",
                        "published_at": pub_el.text if pub_el is not None else None
                    })
    except Exception as e:
        print(f"Error fetching global headlines: {e}")
    return items[:limit]
