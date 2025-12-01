# kobotPick/backEnd/config/settings.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 서버 설정
    API_V1_STR: str = "/api/v1"
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    # 데이터 API 키 (예시. 실제 API 사용 시 필요)
    # ALPHA_VANTAGE_API_KEY: str = "YOUR_ALPHA_VANTAGE_KEY"

    # 캐싱 설정 (나중에 Redis 등을 사용하게 될 경우)
    CACHE_EXPIRATION_SECONDS: int = 300 # 5분 캐시

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()