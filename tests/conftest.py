"""Shared fixtures; each test receives fresh database, Redis, and email state."""

from unittest.mock import AsyncMock
from urllib.parse import urlparse

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from redis_fastapi.cache_backend import CacheBackend
from redis_fastapi.deps import get_cache_backend
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.email import EmailServiceInterface
from app.dependencies import get_email_service
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def redis_client():
    async with fakeredis.aioredis.FakeRedis() as redis:
        yield redis


@pytest.fixture
def cache(redis_client):
    return CacheBackend(redis_client)


@pytest.fixture
def email_service():
    return AsyncMock(spec=EmailServiceInterface)


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield async_sessionmaker(engine, autoflush=False, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.fixture
async def client(session_factory, cache, email_service):
    async def override_get_db():
        async with session_factory() as db:
            yield db

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cache_backend] = lambda: cache
    app.dependency_overrides[get_email_service] = lambda: email_service
    try:
        # The fixture owns the test schema; avoid starting the production database lifespan.
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest.fixture
def user_data():
    return {
        "full_name": "Test User",
        "email": "test@example.com",
        "password": "testpassword",
        "phone": "0901234567",
    }


@pytest.fixture
async def register_user(client, email_service):
    """Return a helper that registers and confirms any supplied user data."""

    async def register(data):
        response = await client.post("/auth/register", json=data)
        assert response.status_code == 201, response.text
        link = email_service.send_confirmation_email.call_args.kwargs[
            "confirmation_link"
        ]
        token = urlparse(link).path.rsplit("/", 1)[-1]
        response = await client.post(f"/auth/confirm/{token}")
        assert response.status_code == 200, response.text
        return data

    return register


@pytest.fixture
async def registered_user(register_user, user_data):
    return await register_user(user_data)


@pytest.fixture
async def auth_client(client, registered_user):
    response = await client.post(
        "/auth/login",
        data={
            "username": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert response.status_code == 200, response.text
    previous_authorization = client.headers.get("Authorization")
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    try:
        yield client
    finally:
        if previous_authorization is None:
            client.headers.pop("Authorization", None)
        else:
            client.headers["Authorization"] = previous_authorization
