from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class StaticSecurityHeadersMiddleware(BaseHTTPMiddleware):
	async def dispatch(self, request: Request, call_next) -> Response:
		response = await call_next(request)
		if request.url.path.startswith("/static"):
			response.headers.setdefault("X-Content-Type-Options", "nosniff")
			response.headers.setdefault("Content-Security-Policy", "default-src 'none'")
		return response
