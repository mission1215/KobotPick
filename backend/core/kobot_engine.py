# backend/core/kobot_engine.py
import random
from typing import List, Dict

# 실제 AI 점수 대신 임시로 랜덤 + 티커 기반 점수 (Yahoo만 있어도 50점 아님!)
def calculate_fake_score(ticker: str) -> int:
    base = hash(ticker) % 100
    return max(60, min(95, base + random.randint(-8, 12)))

def get_top_stocks() -> List[Dict]:
    stocks = [
        ("NVDA", "NVIDIA", "US"), ("TSLA", "Tesla", "US"), ("AAPL", "Apple", "US"),
        ("MSFT", "Microsoft", "US"), ("AMZN", "Amazon", "US"),
        ("005930.KS", "삼성전자", "KR"), ("000660.KS", "SK하이닉스", "KR"),
        ("035420.KS", "NAVER", "KR"), ("005380.KS", "현대차", "KR"),
        ("000270.KS", "기아", "KR"),
        ("SPY", "S&P 500 ETF", "ETF"), ("QQQ", "Invesco QQQ", "ETF"),
        ("TIGER", "TIGER 미국테크", "ETF"), ("VTI", "Vanguard Total", "ETF"),
    ]
    
    result = []
    for ticker, name, country in stocks:
        score = calculate_fake_score(ticker)
        result.append({
            "ticker": ticker,
            "name": name,
            "country": country,
            "score": score,
        })
    return sorted(result, key=lambda x: x["score"], reverse=True)[:15]

def get_picks_with_recommendations():
    return get_top_stocks()

def analyze_and_recommend(ticker: str, full: bool = False, custom_date: str = None):
    score = calculate_fake_score(ticker.upper())
    return {
        "ticker": ticker.upper(),
        "score": score,
        "recommendation": "STRONG BUY" if score >= 80 else "BUY" if score >= 70 else "HOLD",
        "reason": f"AI 분석 점수 {score}점 (임시 엔진)",
    }