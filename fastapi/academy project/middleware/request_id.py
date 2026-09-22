import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("academy.access")


class RequestIDLoggingMiddleware(BaseHTTPMiddleware):
	async def dispatch(self, request: Request, call_next) -> Response:
		request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
		request.state.request_id = request_id

		logger.info(
			"request start id=%s client=%s method=%s path=%s",
			request_id,
			request.client.host if request.client else "unknown",
			request.method,
			request.url.path,
		)

		started = time.perf_counter()
		try:
			response = await call_next(request)
			status_code = response.status_code
		except Exception:
			duration_ms = (time.perf_counter() - started) * 1000
			logger.exception(
				"request error id=%s method=%s path=%s duration_ms=%.2f",
				request_id,
				request.method,
				request.url.path,
				duration_ms,
			)
			raise

		duration_ms = (time.perf_counter() - started) * 1000
		response.headers["X-Request-ID"] = request_id
		response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
		logger.info(
			"request end id=%s method=%s path=%s status=%s duration_ms=%.2f",
			request_id,
			request.method,
			request.url.path,
			status_code,
			duration_ms,
		)
		return response
