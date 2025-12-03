from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
import datetime

from core.kobot_engine import get_top_stocks, analyze_and_recommend
from core.data_handler import get_market_snapshot, get_global_headlines

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Kobot Pick API Running", "time": datetime.datetime.utcnow().isoformat()}

@app.get("/warmup")
def warmup():
    return {"status": "awake", "time": datetime.datetime.utcnow().isoformat()}

@app.get("/api/v1/picks")
async def picks():
    return await run_in_threadpool(get_top_stocks)

@app.get("/api/v1/recommendation/{ticker}")
async def recommendation(ticker: str):
    result = await run_in_threadpool(analyze_and_recommend, ticker.upper())
    return result or {"error": "No data"}

@app.get("/api/v1/market/snapshot")
async def snapshot():
    return await run_in_threadpool(get_market_snapshot)

@app.get("/api/v1/market/headlines")
async def headlines():
    return await run_in_threadpool(get_global_headlines)