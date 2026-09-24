from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.logger import logger
from app.core.config import APP_NAME
from app.db.base import Base
from app.db.database import engine
from app.routers import test, user

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Router imports register models before creating tables for development.
    Base.metadata.create_all(bind=engine)
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(title=APP_NAME, version="1.0.0", lifespan=lifespan)
app.include_router(user.router)
app.include_router(test.router)

@app.get("/")
async def root():
    return {"message": "Hello FastAPI"}


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
