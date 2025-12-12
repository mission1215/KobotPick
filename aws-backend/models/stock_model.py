# kobotPick/backEnd/models/stock_model.py

from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class Fundamentals(BaseModel):
    market_cap: Optional[float] = None
    per: Optional[float] = None
    pbr: Optional[float] = None
    roe: Optional[float] = None
    dividend_yield: Optional[float] = None
    psr: Optional[float] = None


class HistoricalCandle(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float


class NewsItem(BaseModel):
    title: str
    link: str
    publisher: Optional[str] = None
    published_at: Optional[str] = None


class CompanyProfile(BaseModel):
    sector: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    summary: Optional[str] = None
    employees: Optional[int] = None
    exchange: Optional[str] = None
    currency: Optional[str] = None

class RecommendationDetail(BaseModel):
    action: str  # BUY, SELL, HOLD, STRONG_BUY 등
    buy_price: float
    sell_price: float
    stop_loss: float
    rationale: str # 추천 근거 텍스트

class StockRecommendation(BaseModel):
    ticker: str
    name: str
    current_price: float
    last_updated: str
    country: str
    currency: str
    recommendation: RecommendationDetail
    fundamentals: Fundamentals
    historical: List[HistoricalCandle]
    news: List[NewsItem]
    profile: CompanyProfile
    # 향후 market_cap, per 등 펀더멘탈 정보 추가 가능

class PickItem(BaseModel):
    ticker: str
    name: str

    country: str
    score: int

class KobotPicks(BaseModel):
    picks: List[PickItem]
