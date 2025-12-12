import json
import datetime
from typing import Any, Dict, Tuple

from core.kobot_engine import get_top_stocks, analyze_and_recommend
from core.data_handler import get_market_snapshot, get_global_headlines


# -------------------------------
# 공통 유틸
# -------------------------------

def _response(body: Dict[str, Any], status: int = 200) -> Dict[str, Any]:
    """공통 HTTP JSON 응답"""
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",          # FastAPI CORS와 동일하게 전체 허용
            "Access-Control-Allow-Methods": "GET,OPTIONS",
            "Access-Control-Allow-Headers": "*",
        },
        "body": json.dumps(body, ensure_ascii=False, default=str),
    }


def _parse_request(event: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    """
    Lambda 이벤트에서 method, path, query 파라미터를 추출.
    - Function URL, HTTP API 둘 다 최대한 대응
    """
    # path
    path = event.get("rawPath") or event.get("path") or "/"

    # method
    rc = event.get("requestContext") or {}
    http = rc.get("http") or {}
    method = http.get("method") or event.get("httpMethod") or "GET"
    method = method.upper()

    # query
    qs = event.get("queryStringParameters") or {}
    if qs is None:
        qs = {}

    return method, path, qs


def _normalize_path(path: str) -> str:
    """뒤에 붙은 / 때문에 매칭 안 되는 것 방지용"""
    if path != "/" and path.endswith("/"):
        return path[:-1]
    return path


# -------------------------------
# Lambda 핸들러 (FastAPI main.py 대응)
# -------------------------------

def lambda_handler(event, context):
    method, raw_path, qs = _parse_request(event)
    path = _normalize_path(raw_path)

    print(f"[lambda] method={method}, path={path}, qs={qs}")

    # CORS preflight
    if method == "OPTIONS":
        return _response({"status": "ok", "message": "preflight"}, status=200)

    # --------------------------------
    # 1) GET "/"   (root)
    #    FastAPI: root()
    # --------------------------------
    if method == "GET" and path == "/":
        return _response(
            {
                "message": "Kobot Pick API Running",
                "time": datetime.datetime.utcnow().isoformat(),
            }
        )

    # --------------------------------
    # 2) GET "/warmup"
    #    FastAPI: warmup()
    # --------------------------------
    if method == "GET" and path == "/warmup":
        return _response(
            {
                "status": "awake",
                "time": datetime.datetime.utcnow().isoformat(),
            }
        )

    # --------------------------------
    # 3) GET "/api/v1/picks"
    #    FastAPI: picks()
    # --------------------------------
    if method == "GET" and path == "/api/v1/picks":
        try:
            # 원래는 run_in_threadpool(get_top_stocks) 이었으나
            # Lambda에서는 그대로 동기 호출해도 문제 없음.
            picks = get_top_stocks()
            return _response(picks)
        except Exception as e:
            print("[error] /api/v1/picks:", repr(e))
            return _response(
                {"error": "failed to get picks"},
                status=500,
            )

    # --------------------------------
    # 4) GET "/api/v1/recommendation/{ticker}"
    #    FastAPI: recommendation(ticker)
    # --------------------------------
    if method == "GET" and path.startswith("/api/v1/recommendation/"):
        try:
            ticker = path.split("/api/v1/recommendation/")[1].strip()
        except Exception:
            ticker = ""

        if not ticker:
            return _response(
                {"error": "ticker path parameter is required"},
                status=400,
            )

        try:
            result = analyze_and_recommend(ticker.upper())
            return _response(result or {"error": "No data"})
        except Exception as e:
            print("[error] /api/v1/recommendation:", ticker, repr(e))
            return _response(
                {"error": f"failed to analyze {ticker}"},
                status=500,
            )

    # --------------------------------
    # 5) GET "/api/v1/market/snapshot"
    #    FastAPI: snapshot()
    # --------------------------------
    if method == "GET" and path == "/api/v1/market/snapshot":
        try:
            snapshot = get_market_snapshot()
            return _response(snapshot)
        except Exception as e:
            print("[error] /api/v1/market/snapshot:", repr(e))
            return _response(
                {"error": "failed to get market snapshot"},
                status=500,
            )

    # --------------------------------
    # 6) GET "/api/v1/market/headlines?lang=en"
    #    FastAPI: headlines(lang="en")
    # --------------------------------
    if method == "GET" and path == "/api/v1/market/headlines":
        lang = qs.get("lang") or "en"
        try:
            headlines = get_global_headlines(lang)
            return _response(headlines)
        except Exception as e:
            print("[error] /api/v1/market/headlines:", repr(e))
            return _response(
                {"error": "failed to get market headlines"},
                status=500,
            )

    # --------------------------------
    # 7) 404 – 정의되지 않은 경로
    # --------------------------------
    return _response(
        {"error": "Not Found", "path": path},
        status=404,
    )