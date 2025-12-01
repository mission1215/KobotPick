#!/usr/bin/env bash
# 간단 실행 스크립트: 백엔드(FastAPI)와 프런트(http.server)를 함께 띄웁니다.

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT_DIR/.venv"

# 가상환경 체크
if [ ! -d "$VENV" ]; then
  echo "❌ .venv 가 없습니다. 먼저: python3 -m venv .venv && .venv/bin/pip install -r backEnd/requirements.txt"
  exit 1
fi

# 백엔드 실행
cd "$ROOT_DIR/backEnd"
echo "▶️  Starting backend on http://127.0.0.1:8000"
nohup "$VENV/bin/uvicorn" main:app --host 127.0.0.1 --port 8000 > "$ROOT_DIR/uvicorn.log" 2>&1 &
BACK_PID=$!

# 프런트엔드 실행
cd "$ROOT_DIR/frondEnd"
echo "▶️  Starting frontend on http://127.0.0.1:5500"
nohup python3 -m http.server 5500 > "$ROOT_DIR/frontend.log" 2>&1 &
FRONT_PID=$!

echo "✅ backend pid: $BACK_PID"
echo "✅ frontend pid: $FRONT_PID"
echo "로그: uvicorn.log / frontend.log"
echo "정지: kill $BACK_PID $FRONT_PID"
