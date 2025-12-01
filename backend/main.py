# kobotPick/backEnd/main.py

from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from core.kobot_engine import analyze_and_recommend, get_top_stocks, get_picks_with_recommendations
from core.data_handler import get_market_snapshot, get_global_headlines
from config.settings import settings
from models.stock_model import StockRecommendation, PickItem  # Pydantic 모델 import

app = FastAPI(
    title="Kobot Pick API",
    description="주식 추천 Kobot 분석 백엔드 서버"
)

# CORS 설정 (settings 파일에서 관리하는 것이 일반적이나, 여기서는 간단히 *로 설정 유지)
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API 엔드포인트 정의 ---

@app.get("/")
async def root():
    return {"message": "Kobot Pick API is running."}

@app.get(f"{settings.API_V1_STR}/recommendation/{{ticker}}", response_model=StockRecommendation)
async def get_recommendation(ticker: str):
    """특정 종목 티커에 대한 Kobot의 분석 결과를 반환합니다. (상세 화면용)"""
    ticker_upper = ticker.upper()
    result = analyze_and_recommend(ticker_upper, allow_partial=True)

    if result is None:
        raise HTTPException(status_code=404, detail=f"데이터 분석 오류 또는 종목을 찾을 수 없습니다: {ticker_upper}")

    return result

@app.get(f"{settings.API_V1_STR}/picks", response_model=List[PickItem])
async def get_kobot_picks():
    """오늘의 Kobot 추천 종목 리스트를 반환합니다. (홈 화면용)"""
    return get_top_stocks()

@app.get(f"{settings.API_V1_STR}/picks/full")
async def get_kobot_picks_full():
    """추천 + 상세 리코멘드 한번에 반환 (홈 화면 N+1 방지)."""
    return get_picks_with_recommendations()

@app.get(f"{settings.API_V1_STR}/market/snapshot")
async def market_snapshot():
    """주요 지수/환율 요약."""
    return get_market_snapshot()

@app.get(f"{settings.API_V1_STR}/market/headlines")
async def market_headlines():
    """글로벌 시장 뉴스 헤드라인."""
    return get_global_headlines()

# --- 서버 실행 ---
if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.SERVER_HOST, port=settings.SERVER_PORT, reload=True)
