import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, User, get_db
from app.main import app

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


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
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as db:
            yield db

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db
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


async def test_register_user(client, session_factory, user_data):
    response = await client.post("/auth/register", json=user_data)
    assert response.status_code == 201
    assert response.json() == {"message": "User registered successfully"}

    async with session_factory() as db:
        user = await db.scalar(select(User).where(User.email == user_data["email"]))
        assert user is not None
        assert user.full_name == user_data["full_name"]
        assert user.phone == user_data["phone"]
        assert user.hashed_password != user_data["password"]
        assert user.verify_password(user_data["password"])


@pytest.mark.parametrize("duplicate_field", ["email", "phone", "both"])
async def test_register_existing_user(client, session_factory, user_data, duplicate_field):
    response = await client.post("/auth/register", json=user_data)
    assert response.status_code == 201

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
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 1

    # A rejected registration must not break subsequent requests.
    response = await client.post("/auth/register", json={
        **user_data, "email": "new@example.com", "phone": "0909999999",
    })
    assert response.status_code == 201
