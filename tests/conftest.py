"""Shared fixtures; each test receives fresh database, Redis, and email state."""

from datetime import timedelta
from typing import Optional
from unittest.mock import AsyncMock
from urllib.parse import urlparse

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from redis_fastapi.cache_backend import CacheBackend
from redis_fastapi.deps import get_cache_backend
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from decimal import Decimal

from app.core.database import Base, User, UserRole, get_db, Service
from app.services.email_service import EmailServiceInterface
from app.core.security import create_access_token
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


# @pytest.fixture
# def user_data():
#     return {
#         "full_name": "Test User",
#         "email": "test@example.com",
#         "password": "testpassword",
#         "phone": "0901234567",
#     }

@pytest.fixture
def customer_data():
    return {
        "full_name": "Test customer",
        "email": "customer@example.com",
        "password": "customerpassword",
        "phone": "0901234678",
    }

@pytest.fixture
def barber_data():
    return {
        "full_name": "Test barber",
        "email": "barber@example.com",
        "password": "barberpassword",
        "phone": "0901234789",
    }

@pytest.fixture
def admin_data():
    return {
        "full_name": "Test admin",
        "email": "admin@example.com",
        "password": "adminpassword",
        "phone": "0901234890",
    }


@pytest.fixture
async def register_user(session_factory):
    """
        Helper fixture to register a user
    """

    async def register(data):
        # 
        async with session_factory() as db:

            user = User(
                full_name=data["full_name"],
                email=data["email"],
                phone=data["phone"],
                role=data["role"] or UserRole.customer,
            )
            user.hash_password(data["password"])
            db.add(user)
            await db.commit()
            await db.refresh(user)


        return data

    return register


@pytest.fixture
async def registered_user(register_user, customer_data):
    return await register_user(customer_data)


@pytest.fixture
async def create_auth_client_for_user(client, session_factory):
    async def create_client(
        user: User,
    ):
        token = user.create_access_token(expires_delta=timedelta(hours=1), sid=None)
        client.headers.update({"Authorization": f"Bearer {token}"})
        return client

    return create_client



@pytest.fixture
async def customer_user(session_factory, customer_data):
    async with session_factory() as db:
        user = User(
            full_name = customer_data["full_name"],
            email = customer_data["email"],
            phone = customer_data["phone"],
            role=UserRole.customer
        )
        user.hash_password(customer_data["password"])
        db.add(user)
        await db.commit()

    return user

@pytest.fixture
async def barber_user(session_factory, barber_data):
    async with session_factory() as db:
        user = User(
            full_name = barber_data["full_name"],
            email = barber_data["email"],
            phone = barber_data["phone"],
            role=UserRole.barber
        )
        user.hash_password(barber_data["password"])
        db.add(user)
        await db.commit()

    return user

@pytest.fixture
async def admin_user(session_factory, admin_data):
    async with session_factory() as db:
        user = User(
            full_name = admin_data["full_name"],
            email = admin_data["email"],
            phone = admin_data["phone"],
            role=UserRole.admin
        )
        user.hash_password(admin_data["password"])
        db.add(user)
        await db.commit()

    return user

@pytest.fixture
async def sample_services(session_factory):
    services = [
        Service(
            name="Cắt tóc nam",
            description="Cắt tóc nam cơ bản",
            price=Decimal("100000"),
            duration_minutes=30,
            is_active=True,
        ),
        Service(
            name="Cắt tóc nữ",
            description="Cắt tóc nữ cơ bản",
            price=Decimal("120000"),
            duration_minutes=45,
            is_active=True,
        ),
        Service(
            name="Cắt tóc trẻ em",
            description=None,
            price=Decimal("80000"),
            duration_minutes=20,
            is_active=False,
        ),
    ]
    async with session_factory() as db:
        db.add_all(services)
        await db.commit()
        for service in services:
            await db.refresh(service)
    return services
