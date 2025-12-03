# backend/main.py

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from cache import cache
from config.settings import settings
from core.kobot_engine import (
    analyze_and_recommend,
    get_picks_with_recommendations,
    get_top_stocks,
)
from core.data_handler import get_global_headlines, get_market_snapshot

API_PREFIX = settings.API_V1_STR

app = FastAPI(
    title="Kobot Pick API",
    version="1.0.0",
    description="Render Free 플랜에서도 빠르게 깨어나도록 최적화된 버전",
)

# Vercel + 로컬 모두 허용
origins = [
    "http://127.0.0.1:5500",
    "http://localhost:3000",
    "http://localhost:5500",
    "https://kobot-pick.vercel.app",
    "https://kobotpick.onrender.com",  # 자기 자신도 허용
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Kobot Pick API awake & ready!", "time": __import__('time').time()}

# 이 엔드포인트가 제일 중요 → UptimeRobot이 5~10분마다 호출하면 절대 안 잠
@app.get("/warmup")
async def warmup():
    # 아주 가볍게만 실행해서 서버 깨우기
    return {"status": "awake", "time": __import__('datetime').datetime.utcnow().isoformat() + "Z"}

@app.get(f"{API_PREFIX}/picks")
@cache(ttl=300)
async def picks():
    return await run_in_threadpool(get_top_stocks)

@app.get(f"{API_PREFIX}/picks/full")
@cache(ttl=300)
async def picks_with_rec():
    return await run_in_threadpool(get_picks_with_recommendations)

@app.get(f"{API_PREFIX}/recommendation/{{ticker}}")
@cache(ttl=300)
async def recommendation(ticker: str):
    rec = await run_in_threadpool(analyze_and_recommend, ticker, True, None)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec

@app.get(f"{API_PREFIX}/market/snapshot")
@cache(ttl=120)
async def market_snapshot():
    return await run_in_threadpool(get_market_snapshot)

@app.get(f"{API_PREFIX}/market/headlines")
@cache(ttl=300)
async def market_headlines():
    return await run_in_threadpool(get_global_headlines, 8)