# backend/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 🔽 네 프로젝트에 맞게 임포트 부분만 맞춰줘
# 예시:
# from routers.picks import router as picks_router
# from routers.market import router as market_router
# from routers.recommendation import router as recommendation_router
# from routers.dashboard import router as dashboard_router

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