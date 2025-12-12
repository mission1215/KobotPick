# kobotPick/backEnd/core/utils.py

import pandas as pd
import pandas_ta as ta
import numpy as np

def calculate_technical_indicators(hist_df: pd.DataFrame) -> pd.DataFrame:
    """주가 데이터프레임에 볼린저 밴드(BB), RSI 등의 지표를 추가합니다."""
    # 볼린저 밴드 (20일 기준)
    hist_df.ta.bbands(close='Close', length=20, append=True)
    # RSI (14일 기준)
    hist_df.ta.rsi(close='Close', length=14, append=True)

    # 이동 평균선 추가
    hist_df.ta.sma(close='Close', length=20, append=True, alias='SMA_20')
    hist_df.ta.sma(close='Close', length=5, append=True, alias='SMA_5')
    hist_df.ta.sma(close='Close', length=60, append=True, alias='SMA_60')

    return hist_df

def create_json_response(data: dict) -> dict:
    """결과 데이터를 API 응답 형식으로 정리합니다. (로깅/보안 등 추가 가능)"""
    # 현재는 단순히 데이터를 반환하지만, 나중에 추가 로직이 필요할 수 있습니다.
    return data
