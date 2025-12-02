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

# 🔽 네 프로젝트에 맞게 임포트 부분만 맞춰줘
# 예시:
# from routers.picks import router as picks_router
# from routers.market import router as market_router
# from routers.recommendation import router as recommendation_router
# from routers.dashboard import router as dashboard_router

API_PREFIX = settings.API_V1_STR

app = FastAPI(
    title="Kobot Pick API",
    version="1.0.0",
)

# CORS 설정 (이미 있다면 중복 추가 말고 기존 것만 유지해도 됨)
origins = [
    "http://127.0.0.1:5500",             # 로컬 개발 (VSCode Live Server 등)
    "http://localhost:5500",
    "http://localhost:3000",
    "https://kobot-pick.vercel.app",      # Vercel 프론트
    # 필요하면 도메인 추가: "https://kobotpick.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔽 라우터 등록 (네 프로젝트에 맞게 살려줘)
# app.include_router(picks_router, prefix="/api/v1", tags=["picks"])
# app.include_router(market_router, prefix="/api/v1/market", tags=["market"])
# app.include_router(recommendation_router, prefix="/api/v1", tags=["recommendation"])
# app.include_router(dashboard_router, prefix="/api/v1", tags=["dashboard"])


@app.get(f"{API_PREFIX}/picks")
@cache(ttl=300)
async def picks():
    """해외/국내/ETF 추천 리스트 (스코어만)."""
    return await run_in_threadpool(get_top_stocks)


@app.get(f"{API_PREFIX}/picks/full")
@cache(ttl=300)
async def picks_with_rec():
    """추천 리스트 + 개별 리포트까지 포함."""
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
    """주요 지수/환율 요약."""
    return await run_in_threadpool(get_market_snapshot)


@app.get(f"{API_PREFIX}/market/headlines")
@cache(ttl=300)
async def market_headlines():
    """글로벌 뉴스 헤드라인."""
    return await run_in_threadpool(get_global_headlines, 8)


@app.get("/")
async def root():
    return {"message": "Kobot Pick API running"}


# ✅ 여기만 실제로 새로 추가되는 엔드포인트 (Warmup용)
@app.get("/warmup")
async def warmup():
    """
    Render Free 플랜 콜드스타트 줄이기용 헬스 체크 엔드포인트.
    매우 가벼운 연산만 수행.
    """
    return {"status": "awake"}


# Uvicorn에서 main:app 으로 실행
# uvicorn main:app --host 0.0.0.0 --port 8000
