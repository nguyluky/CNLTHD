from re import A
from urllib import response

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, User, UserRole, get_db
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

@pytest.fixture
async def auth_client(client, session_factory, user_data):

    async with session_factory() as db:
        user = User(
            full_name = user_data["full_name"],
            email = user_data["email"],
            phone = user_data["phone"],
            role=UserRole.customer
        )
        user.hash_password(user_data["password"])
        db.add(user)
        await db.commit()

    #login to get the token
    login_response = await client.post("/auth/login", data={
        "username": user_data["email"],
        "password": user_data["password"]
    })

    token = login_response.json()["access_token"]

    client.headers = {"Authorization": f"Bearer {token}"}

    yield client

    client.headers.pop("Authorization", None)

async def test_get_user_profile(auth_client, user_data):
    response = await auth_client.get("/users/me")

    # response data must match and the user must be active
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == user_data["email"]
    assert data["phone"] == user_data["phone"]
    assert data["full_name"] == user_data["full_name"]
    assert data["is_active"] == True

async def test_update_profile_success(auth_client, user_data):
    new_profile = {
        "full_name": "New Test User",
    }

    response = await auth_client.patch("/users/me", json=new_profile)

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] != user_data["full_name"]

async def test_update_profile_fail(auth_client, session_factory, user_data):
    another_user = {
        "full_name": "Another User",
        "email": "another@example.com",
        "password": "anotherpassword",
        "phone": "0907654321",
    }

    # register a different user
    await auth_client.post("/auth/register", json=another_user)

    conflict_payload = {
        "email": another_user["email"]
    }

    response = await auth_client.patch("/users/me", json=conflict_payload)

    assert response.status_code == 409 
    assert response.json()["message"] == "This email is currently being used by a different user"

    # making sure the user's profile stays the same
    async with session_factory() as db:
        user_in_db = await db.scalar(select(User).where(User.email == user_data["email"]))
        assert user_in_db is not None

async def test_update_user_password_success(auth_client, user_data):
    request = {
        "old_password": user_data["password"],
        "new_password": "newtestpassword"
    }

    response = await auth_client.put("/users/me/password", json=request)
    assert response.status_code == 204

async def test_update_user_password_fail(auth_client, user_data):
    # oldpassword is incorrect
    invalid_oldpass_request = {
        "old_password": "wrongpassword",
        "new_password": "newtestpassword"
    }

    response = await auth_client.put("/users/me/password", json=invalid_oldpass_request)
    assert response.status_code == 400
    assert response.json()["message"] == "Old password is invalid"

    # oldpassword is incorrect
    invalid_newpass_request = {
        "old_password": user_data["password"],
        "new_password": user_data["password"]
    }

    response = await auth_client.put("/users/me/password", json=invalid_newpass_request)
    assert response.status_code == 422



