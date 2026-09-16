from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import APP_NAME
from app.db.base import Base
from app.db.database import engine
from app.routers import user


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


@app.get("/")
async def root():
    return {"message": "Hello FastAPI"}


@app.get("/health")
async def health():
    return {"status": "ok"}
