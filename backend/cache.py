# backend/cache.py

import time
from functools import wraps

# 간단한 메모리 캐시 저장소
CACHE_STORE = {}

def cache(ttl: int = 60):
    """
    ttl초 동안 함수 결과를 캐싱하는 데코레이터.
    - I/O 많은 함수
    - 외부 API 호출이 많은 함수 (yfinance, News, Profile 등)
    - Dashboard 전체 계산
    - 종목 추천 로직
    에서 큰 속도 효과.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{args}:{kwargs}"
            now = time.time()

            # 캐시가 있고, 아직 TTL 안 지났다면 → 캐시 리턴
            if key in CACHE_STORE:
                saved_time, saved_value = CACHE_STORE[key]
                if now - saved_time < ttl:
                    return saved_value

            # 아니면 새로 계산
            value = await func(*args, **kwargs)

            # 저장
            CACHE_STORE[key] = (now, value)
            return value

        return wrapper
    return decorator