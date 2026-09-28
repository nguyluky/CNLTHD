from contextlib import asynccontextmanager
import http

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from redis_fastapi import FastAPIRedis

from app.core.exception import ErrorModel, ValidationErrorModel
from app.core.logger import logger
from app.core.config import APP_NAME
from app.core.database import Base
from app.core.database import engine
from app.internal import user
from app.routers import test, auth

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Router imports register models before creating tables for development.
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield
    finally:
        await engine.dispose()


origins = [
    "http://localhost",
    "http://localhost:8080",
]

app = FastAPI(title=APP_NAME, version="1.0.0", lifespan=lifespan, responses={
    500: {
        "model": ErrorModel,
        "description": "Internal Server Error"
    },
    422: {
        "model": ValidationErrorModel,
        "description": "Validation Error"
    },
})
FastAPIRedis(app).lifespan()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(user.router)
# app.include_router(test.router)
app.include_router(auth.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exception: Exception):
    logger.error(f"Unhandled Exception on {request.method} {request.url}: {exception}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "A system error has occured, please try again later."
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exception: HTTPException):
    return JSONResponse(
        status_code=exception.status_code,
        content={
            "error_code": http.HTTPStatus(exception.status_code).name,
            "message": exception.detail
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    message = "Validation errors:"
    for error in exc.errors():
        message += f"\nField: {error['loc']}, Error: {error['msg']}"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": message,
            "details": exc.errors()
        }
    )
