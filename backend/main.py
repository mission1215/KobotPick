# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
import datetime

from core.kobot_engine import (
    get_top_stocks,
    get_picks_with_recommendations,
    analyze_and_recommend,
)
from core.data_handler import get_market_snapshot, get_global_headlines

app = FastAPI(title="Kobot Pick API", version="1.0")

# Vercel + 로컬 + Render 모두 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Kobot Pick API is ALIVE!", "time": datetime.datetime.utcnow().isoformat() + "Z"}

@app.get("/warmup")
async def warmup():
    return {"status": "awake", "time": datetime.datetime.utcnow().isoformat() + "Z"}

@app.get("/api/v1/picks")
async def picks():
    data = await run_in_threadpool(get_top_stocks)
    return data

@app.get("/api/v1/picks/full")
async def picks_full():
    data = await run_in_threadpool(get_picks_with_recommendations)
    return data

@app.get("/api/v1/recommendation/{ticker}")
async def recommendation(ticker: str):
    rec = await run_in_threadpool(analyze_and_recommend, ticker.upper(), True, None)
    if not rec:
        return {"error": "Not found"}
    return rec

@app.get("/api/v1/market/snapshot")
async def snapshot():
    return await run_in_threadpool(get_market_snapshot)

@app.get("/api/v1/market/headlines")
async def headlines():
    return await run_in_threadpool(get_global_headlines, 8)