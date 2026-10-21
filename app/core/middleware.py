import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

access_logger = logging.getLogger("app.access")

class AccessLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, 
        request: Request, 
        call_next
    ):
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:
            process_time = time.perf_counter() - start_time
            duration_ms = round(process_time * 1000, 2)

            access_logger.error(
                f"{request.method} {request.url.path} failed with unhandled exception - {duration_ms}ms",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "error": str(exc)
                },
                exc_info=True
            )
            raise exc

        process_time = time.perf_counter() - start_time
        duration_ms = round(process_time * 1000, 2)

        response.headers["X-Process-Time"] = f"{duration_ms}ms"

        access_logger.info(
            f"{request.method} {request.url.path}{"?" if request.url.query else ""}{request.url.query} - Status: {response.status_code} - {duration_ms}ms",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            }
        )
        
        return response