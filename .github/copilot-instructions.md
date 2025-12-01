# KobotPick — Copilot Instructions

간단 요약
- 백엔드는 `backEnd/`에, 프런트엔드 정적 파일은 `frondEnd/`에 있음.
- 핵심 흐름: 프런트엔드(`frondEnd/js/main_dashboard.js`)가 백엔드 API(`backEnd/main.py`)의 `/api/v1/picks` 및 `/api/v1/recommendation/{ticker}`를 호출.

아키텍처(빅픽처)
- API 레이어: `backEnd/main.py` — FastAPI 앱과 라우트 정의. 응답 스키마는 Pydantic 모델(`backEnd/models/stock_model.py`)을 사용.
- 비즈니스 로직: `backEnd/core/kobot_engine.py` — 종목 분석 및 추천 로직이 위치. 데이터 수집/가공 함수는 여기서 호출.
- 데이터 수집: `backEnd/core/data_handler.py` — `yfinance` 사용. `get_historical_data`, `get_stock_info` 제공.
- 지표 계산: `backEnd/core/utils.py` — `pandas_ta`로 기술적 지표(BB, RSI, SMA 등)를 계산.
- 프런트엔드: `frondEnd/index.html`, `frondEnd/js/*.js` — 정적 페이지에서 API를 호출해 UI 렌더링.

핵심 실행 및 개발 워크플로우
- 의존성 설치:
  - `cd backEnd && pip install -r requirements.txt`
- 개발 서버 실행(핫리로드):
  - `python backEnd/main.py` 또는
  - (직접) `uvicorn main:app --reload --host 0.0.0.0 --port 8000` (작업 디렉터리를 `backEnd/`에 둠)
- 환경 변수:
  - `backEnd/config/settings.py`는 `pydantic-settings`를 사용해 `.env`를 로드함. 민감 정보(예: API 키)를 `.env`에 둠.
- 프런트엔드 로컬 확인:
  - 정적 파일을 브라우저로 열면 `frondEnd/js/main_dashboard.js`가 `http://127.0.0.1:8000/api/v1/`를 호출하므로 백엔드가 실행 중이어야 함.

프로젝트 규약 및 패턴(에이전트용)
- 라우트는 `backEnd/main.py`에서 정의된다. 새로운 엔드포인트를 만들 땐 `response_model`로 Pydantic 모델을 명시함(예: `StockRecommendation`).
- 도메인 로직은 `core/`에 둔다 — 라우트 함수는 단순히 core의 함수 호출 결과를 반환해야 함.
- 데이터 접근은 `data_handler.py`를 통해 표준화: 외부 API 호출/에러는 이 레이어에서 처리.
- 기술적 지표 계산은 `utils.calculate_technical_indicators`로 통일되어 있어야 하며, pandas DataFrame을 입력/출력으로 사용.
- 프런트엔드와의 계약: API 경로는 `settings.API_V1_STR`로 제어됨. 프런트엔드에서 `API_BASE_URL`을 변경할 경우 동일한 값으로 맞춰야 함.

주의사항 / 알려진 한계
- `yfinance.info`의 `currentPrice`가 None일 수 있음 — `kobot_engine.analyze_and_recommend`는 이를 체크하고 None인 경우 `None` 반환.
- CORS가 현재 `*`로 열려 있음(`main.py`) — 보안 배포 전 검토 필요.
- 캐시(예: Redis)는 현재 미구현. `settings.CACHE_EXPIRATION_SECONDS`만 존재.

구체적 코드 예시(참조)
- 추천 엔드포인트 호출 예시:
  - GET `http://127.0.0.1:8000/api/v1/recommendation/AAPL`
  - 결과 형식은 `backEnd/models/stock_model.py`의 `StockRecommendation` 구조를 따름.
- 기술 지표 호출 위치: `backEnd/core/kobot_engine.py` → `calculate_technical_indicators(hist)`

작업 가이드라인(PR/수정 시)
- API 변경 시 `backEnd/models/stock_model.py`의 Pydantic 모델을 먼저 갱신하고, `response_model`을 업데이트하세요.
- 외부 API 키 등은 `.env`에 추가하고 `settings.py`에서 읽게 하세요. 테스트용 하드코딩 키는 커밋하지 마세요.
- 새로운 dependencies 추가 시 `backEnd/requirements.txt`를 갱신하세요.

요청 피드백
- 이 파일에 빠진 정보나 더 자세히 적었으면 하는 부분(예: 배포/CI 명령, 테스트 구조 등)을 알려주세요. 추가 예시나 명확한 코드를 넣어 병합하겠습니다.
