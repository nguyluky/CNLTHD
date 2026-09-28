from unittest.mock import AsyncMock
from urllib.parse import urlparse
from uuid import UUID

import pytest

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
import fakeredis.aioredis
from redis_fastapi.deps import get_cache_backend
from redis_fastapi.cache_backend import CacheBackend

from app.core.database import Base, User, get_db
from app.core.config import config
from app.core.email import EmailServiceInterface
from app.core.security import decode_access_token
from app.dependencies import get_email_service
from app.main import app

pytestmark = pytest.mark.anyio


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


def confirmation_token(email_service):
    link = email_service.send_confirmation_email.call_args.kwargs["confirmation_link"]
    return urlparse(link).path.rsplit("/", 1)[-1]


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
            transport=ASGITransport(app=app), base_url="http://test",
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


async def test_register_user(
    client, session_factory, user_data, cache, redis_client, email_service,
):
    response = await client.post("/auth/register", json=user_data)
    assert response.status_code == 201
    assert response.json() == {
        "message": "User registered successfully. Please check your email to confirm your registration."
    }
    token = confirmation_token(email_service)
    assert str(UUID(token)) == token
    email_service.send_confirmation_email.assert_awaited_once_with(
        to=user_data["email"],
        confirmation_link=f"{config.BASE_URL}/auth/confirm/{token}",
    )
    assert await cache.get(f"register:{token}", eviction_group="register") == user_data
    keys = await redis_client.keys(f"*register:{token}")
    assert len(keys) == 1
    assert 0 < await redis_client.ttl(keys[0]) <= 3600
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 0


async def test_confirm_registration(client, session_factory, user_data, cache, email_service):
    """
    nghiệm vụ: 
    1. gọi POST /auth/register để tạo token
    2. gọi POST /auth/confirm/{token} để xác nhận đăng ký tạo user trong database
    3. kiểm tra token đã bị xóa khỏi cache và Redis | user đã được tạo trong database
    """
    
    response = await client.post("/auth/register", json=user_data)
    assert response.status_code == 201
    token = confirmation_token(email_service)
    response = await client.post(f"/auth/confirm/{token}")
    assert response.status_code == 200
    assert response.json() == {"message": "User registered successfully"}
    assert await cache.get(f"register:{token}", eviction_group="register") is None

    async with session_factory() as db:
        user = await db.scalar(select(User).where(User.email == user_data["email"]))
        assert user is not None
        assert user.full_name == user_data["full_name"]
        assert user.phone == user_data["phone"]
        assert user.hashed_password != user_data["password"]
        assert user.verify_password(user_data["password"])

    response = await client.post(f"/auth/confirm/{token}")
    assert response.status_code == 404
    assert response.json()["message"] == "Token not found or expired"
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 1


@pytest.mark.parametrize("duplicate_field", ["email", "phone", "both"])
async def test_register_existing_user(client, session_factory, user_data, duplicate_field, email_service):
    """
    nghiệm vụ:
    1. đầu tiên là tạo một user mới bằng cách gọi POST /auth/register
    2. xác nhận user bằng cách gọi POST /auth/confirm/{token}
    3. sau đó thử đăng ký một user khác với cùng email hoặc phone hoặc cả hai, và kiểm tra rằng server trả về lỗi 409 Conflict
    4. xác nhận rằng email_service.send_confirmation_email không được gọi và số lượng user trong database vẫn là 1
    """
    
    response = await client.post("/auth/register", json=user_data)
    assert response.status_code == 201

    response = await client.post(f"/auth/confirm/{confirmation_token(email_service)}")
    assert response.status_code == 200
    email_service.reset_mock()

    other_user = {
        **user_data,
        "full_name": "Another User",
        "email": "another@example.com",
        "phone": "0907654321",
    }
    for field in ("email", "phone"):
        if duplicate_field in (field, "both"):
            other_user[field] = user_data[field]

    response = await client.post("/auth/register", json=other_user)
    assert response.status_code == 409
    assert response.json()["message"] == "User already exists"
    email_service.send_confirmation_email.assert_not_awaited()
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 1

    # A rejected registration must not break subsequent requests.
    response = await client.post("/auth/register", json={
        **user_data, "email": "new@example.com", "phone": "0909999999",
    })
    assert response.status_code == 201


@pytest.mark.parametrize("missing_field", ["full_name", "email", "password", "phone"])
async def test_register_missing_field(client, user_data, missing_field, email_service, redis_client):
    del user_data[missing_field]
    response = await client.post("/auth/register", json=user_data)
    assert response.status_code == 400
    assert response.json()["error_code"] == "VALIDATION_ERROR"
    email_service.send_confirmation_email.assert_not_awaited()
    assert await redis_client.dbsize() == 0


async def test_confirm_unknown_token(client, session_factory):
    response = await client.post("/auth/confirm/unknown-token")
    assert response.status_code == 404
    assert response.json()["message"] == "Token not found or expired"
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 0


async def test_confirm_expired_token(client, user_data, email_service, redis_client, session_factory):
    response = await client.post("/auth/register", json=user_data)
    assert response.status_code == 201
    token = confirmation_token(email_service)
    keys = await redis_client.keys(f"*register:{token}")
    assert len(keys) == 1
    # Expire immediately without a timing-dependent sleep.
    await redis_client.pexpire(keys[0], 0)
    response = await client.post(f"/auth/confirm/{token}")
    assert response.status_code == 404
    assert response.json()["message"] == "Token not found or expired"
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 0


@pytest.fixture
async def registered_user(client, user_data, email_service):
    response = await client.post("/auth/register", json=user_data)
    assert response.status_code == 201
    response = await client.post(f"/auth/confirm/{confirmation_token(email_service)}")
    assert response.status_code == 200
    return user_data


async def test_login(client, registered_user):
    response = await client.post("/auth/login", data={
        "username": registered_user["email"], "password": registered_user["password"],
    })
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Login successful"
    assert body["email"] == registered_user["email"]
    assert body["token_type"] == "bearer"
    payload = decode_access_token(body["access_token"])
    assert payload["sub"] == registered_user["email"]
    assert payload["role"] == "customer"
    assert "exp" in payload


@pytest.mark.parametrize("field,value", [
    ("username", "unknown@example.com"), ("password", "wrong-password"),
])
async def test_login_invalid_credentials(client, registered_user, field, value):
    credentials = {
        "username": registered_user["email"], "password": registered_user["password"],
    }
    credentials[field] = value
    response = await client.post("/auth/login", data=credentials)
    assert response.status_code == 401
    assert response.json()["message"] == "Invalid email or password"
    assert "access_token" not in response.json()


async def test_login_unconfirmed_user(client, user_data):
    response = await client.post("/auth/register", json=user_data)
    assert response.status_code == 201
    response = await client.post("/auth/login", data={
        "username": user_data["email"], "password": user_data["password"],
    })
    assert response.status_code == 401
    assert response.json()["message"] == "Invalid email or password"
