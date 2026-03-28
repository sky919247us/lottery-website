"""
簡易 IP-based Rate Limiting Middleware
針對寫入型公開端點限制每 IP 每分鐘的請求數
"""
import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# 需要限流的路徑前綴和每分鐘上限
RATE_LIMITS = {
    "/api/map/checkin": 30,
    "/api/map/retailer/": 60,
    "/api/rating": 20,
    "/api/inventory/report": 20,
    "/api/inventory/retailer/": 60,
    "/api/auth/line": 10,
    "/api/merchant/claim": 10,
    "/api/upload": 10,
}

# {ip: {path_prefix: [(timestamp, ...)]}}
_request_log: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 只限制 POST/PUT/DELETE
        if request.method not in ("POST", "PUT", "DELETE"):
            return await call_next(request)

        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"

        # 找到匹配的限流規則
        limit = None
        matched_prefix = None
        for prefix, max_rpm in RATE_LIMITS.items():
            if path.startswith(prefix):
                limit = max_rpm
                matched_prefix = prefix
                break

        if limit is None:
            return await call_next(request)

        now = time.time()
        window = 60  # 1 分鐘視窗

        # 清理過期記錄
        log = _request_log[client_ip][matched_prefix]
        _request_log[client_ip][matched_prefix] = [t for t in log if now - t < window]
        log = _request_log[client_ip][matched_prefix]

        if len(log) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "請求過於頻繁，請稍後再試"},
            )

        log.append(now)
        return await call_next(request)
