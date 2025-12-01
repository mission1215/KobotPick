# KobotPick

FastAPI + Vanilla JS 기반 주식 추천/분석 서비스.

## 구조

- `backend/` : FastAPI 기반 API 서버
- `frontend/` : 정적 HTML/JS/CSS 기반 웹 UI

## 로컬 실행 방법

### 백엔드

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload