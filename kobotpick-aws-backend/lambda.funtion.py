import json
from datetime import datetime, timezone
from typing import Dict, Any


def _json_response(body: Dict[str, Any], status_code: int = 200) -> Dict[str, Any]:
    """공통 HTTP JSON 응답 헬퍼"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            # 나중에 Vercel 프론트에서 호출할 수 있도록 CORS 허용
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def handle_health(event: Dict[str, Any]) -> Dict[str, Any]:
    """GET / 또는 GET /health"""
    return _json_response(
        {
            "status": "ok",
            "service": "kobotpick-aws-backend",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


def handle_headlines(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    GET /headlines – 일단은 더미 데이터
    나중에 Render 백엔드 로직을 옮겨올 자리를 여기로 쓰면 됨.
    """
    headlines = [
        {"id": 1, "title": "Dummy headline 1", "ticker": "AAPL"},
        {"id": 2, "title": "Dummy headline 2", "ticker": "TSLA"},
    ]
    return _json_response(
        {
            "status": "ok",
            "count": len(headlines),
            "items": headlines,
        }
    )


def handle_not_found(path: str) -> Dict[str, Any]:
    """정의되지 않은 path 처리"""
    return _json_response(
        {
            "status": "error",
            "message": f"Path not found: {path}",
        },
        status_code=404,
    )


def lambda_handler(event, context):
    """
    Lambda Function URL로 들어온 요청을 path/method 기준으로 라우팅.
    """
    request_context = event.get("requestContext", {})
    http_info = request_context.get("http", {})

    method = http_info.get("method", "GET")
    path = event.get("rawPath") or http_info.get("path") or "/"

    print(f"[KOBOT] method={method} path={path}")

    if method == "GET":
        if path in ("/", "/health"):
            return handle_health(event)
        if path == "/headlines":
            return handle_headlines(event)

    return handle_not_found(path)