import asyncio
from contextlib import asynccontextmanager
import http

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from redis_fastapi import FastAPIRedis

from app.core.middleware import AccessLoggingMiddleware
from app.schemas.common import create_error_response, ErrorModel, ValidationErrorModel, create_validation_error_response
from app.core.logger import configure_logging, service_logger, shutdown_logging
from app.core.config import configEnv
from app.core.database import Base
from app.core.database import engine
from app.routers import router, domain_exception_handler
from app.core.exception import DomainException


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start logging before initializing application components.
    configure_logging()
    monitor_task = asyncio.create_task(monitor_event_loop())

    # Router imports register models before creating tables for development.
    try:
        async with engine.begin() as connection:
            service_logger.info("Connecting to the database successfully...")
        yield
    finally:
        await engine.dispose()
        
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        await asyncio.to_thread(shutdown_logging)


origins = [
    "http://localhost",
    "http://localhost:8080",
]

app = FastAPI(
    title=configEnv.APP_NAME,
    version="1.0.0",
    description="""
    CNLTHD is a backend API for a hair salon's service management and scheduling system. 
    The system enables customers to search for services, select barbers, and book appointments; it also helps barbers manage their work schedules and allows administrators to manage users, services, and appointments.
    """,
    lifespan=lifespan,
    responses={
        500: {"model": ErrorModel, "description": "Internal Server Error"},
        400: {"model": ValidationErrorModel, "description": "Validation Error"},
    },
)
FastAPIRedis(app).lifespan()
FastAPIRedis(app).lifespan().caching()
FastAPIRedis(app).lifespan().rate_limiting()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AccessLoggingMiddleware)

app.include_router(router)

app.add_exception_handler(
    DomainException,
    domain_exception_handler
)

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exception: Exception):
    service_logger.error(
        f"Unhandled Exception on {request.method} {request.url}: {exception}",
        exc_info=True,
    )
    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="INTERNAL_SERVER_ERROR",
        message="A system error has occurred, please try again later.",
    )   

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exception: HTTPException):
    return create_error_response(
        status_code=exception.status_code,
        error_code=http.HTTPStatus(exception.status_code).name,
        message=exception.detail,
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    message = "Validation errors:"
    sanitized_errors = []

    for error in exc.errors():
        message += f"\nField: {error['loc']}, Error: {error['msg']}"
        error_copy = error.copy()

        if "ctx" in error_copy:
            error_copy["ctx"] = {
                k: (str(v) if isinstance(v, Exception) else v)
                for k, v in error_copy["ctx"].items()
            }

        sanitized_errors.append(error_copy)


    return create_validation_error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        error_code="VALIDATION_ERROR",
        message=message,
        details=sanitized_errors,
    )


async def monitor_event_loop(interval: float = 0.05) -> None:
    loop = asyncio.get_running_loop()
    expected = loop.time() + interval

    while True:
        await asyncio.sleep(interval)

        now = loop.time()
        lag = now - expected

        if lag > 0.1:
            service_logger.warning(
                "Event loop lag detected: %.1f ms",
                lag * 1000,
            )

        expected = now + interval
