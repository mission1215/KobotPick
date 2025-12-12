#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT_DIR/.venv"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

# 가상환경 체크
if [ ! -d "$VENV" ]; then
  echo "❌ .venv 가 없습니다. 먼저: python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt (또는 aws-backend/requirements.txt)"
  exit 1
fi

# 백엔드 실행
BACK_PID=""
if [ -d "$BACKEND_DIR" ]; then
  cd "$BACKEND_DIR"
  echo "▶️  Starting backend on http://127.0.0.1:8000"
  nohup "$VENV/bin/uvicorn" main:app --host 127.0.0.1 --port 8000 > "$ROOT_DIR/uvicorn.log" 2>&1 &
  BACK_PID=$!
else
  echo "⚠️  backend 디렉터리를 찾을 수 없어 백엔드 실행을 건너뜁니다."
fi

# 프런트엔드 실행
if [ ! -d "$FRONTEND_DIR" ]; then
  echo "❌ frontend 디렉터리를 찾을 수 없습니다."
  exit 1
fi
cd "$FRONTEND_DIR"
echo "▶️  Starting frontend on http://127.0.0.1:5500"
nohup python3 -m http.server 5500 > "$ROOT_DIR/frontend.log" 2>&1 &
FRONT_PID=$!

if [ -n "$BACK_PID" ]; then
  echo "✅ backend pid: $BACK_PID"
fi
echo "✅ frontend pid: $FRONT_PID"
echo "로그: uvicorn.log / frontend.log"
echo "정지: kill ${BACK_PID:+$BACK_PID }$FRONT_PID"
