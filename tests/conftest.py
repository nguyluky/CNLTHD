"""Shared fixtures; each test receives fresh database, Redis, and email state."""

from datetime import date, datetime, time, timedelta
from unittest import mock
from unittest.mock import AsyncMock, patch
import fakeredis
import pytest
from httpx import ASGITransport, AsyncClient
from redis_fastapi import get_async_redis
from redis_fastapi.cache_backend import CacheBackend
from asgi_lifespan import LifespanManager
from redis_fastapi.deps import get_cache_backend
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from decimal import Decimal

from app.core.database import BarberSchedule, Base, Booking, BookingService, BookingStatus, User, UserRole, get_db, Service
from app.services.email_service import EmailServiceInterface
from app.dependencies import get_email_service
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def redis_client():
    async with fakeredis.aioredis.FakeRedis(decode_responses=True) as redis_client:
        yield redis_client


# @pytest.fixture(autouse=True)
# async def mock_redis_lifespan(redis_client):
#     """
#     Patches redis.asyncio.Redis.from_url so that redis_fastapi's 
#     lifespan startup initializes with our FakeRedis instance instead of localhost:6379.
#     """
#     with patch("redis.asyncio.Redis.from_url", return_value=redis_client):
#         yield redis_client


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
async def client(
    session_factory, 
    cache, 
    redis_client, 
    email_service
):
    async def override_get_db():
        async with session_factory() as db:
            yield db

    async def override_get_redis():
        return redis_client

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_async_redis] = override_get_redis
    app.dependency_overrides[get_cache_backend] = lambda: cache
    app.dependency_overrides[get_email_service] = lambda: email_service
    try:
        # The fixture owns the test schema; avoid starting the production database lifespan.
        async with LifespanManager(app) as manager:
            async with AsyncClient(
                transport=ASGITransport(app=manager.app),
                base_url="http://test",
            ) as client:
                yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)

@pytest.fixture
def customer_dataA():
    return {
        "full_name": "Test customerA",
        "email": "customera@example.com",
        "password": "customerpassword",
        "phone": "0901234678",
    }

@pytest.fixture
def barber_dataA():
    return {
        "full_name": "Test barberA",
        "email": "barbera@example.com",
        "password": "barberpassword",
        "phone": "0901234789",
    }

@pytest.fixture
def customer_dataB():
    return {
        "full_name": "Test customerB",
        "email": "customerb@example.com",
        "password": "customerpassword",
        "phone": "0901234123",
    }

@pytest.fixture
def barber_dataB():
    return {
        "full_name": "Test barberB",
        "email": "barberb@example.com",
        "password": "barberpassword",
        "phone": "0901234456",
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

    async def register(data: dict):
        # 
        async with session_factory() as db:

            user = User(
                full_name=data["full_name"],
                email=data["email"],
                phone=data["phone"],
                role=data.get("role", UserRole.customer)
            )
            user.hash_password(data["password"])
            db.add(user)
            await db.commit()
            await db.refresh(user)


        return data

    return register


@pytest.fixture
async def registered_user(register_user, customer_dataA):
    return await register_user(customer_dataA)


@pytest.fixture
async def create_auth_client_for_user(client):
    async def create_client(
        user: User,
    ):
        token = user.create_access_token(expires_delta=timedelta(hours=1), sid=None)
        client.headers.update({"Authorization": f"Bearer {token}"})
        return client

    return create_client



@pytest.fixture
async def customer_userA(session_factory, customer_dataA):
    async with session_factory() as db:
        user = User(
            full_name = customer_dataA["full_name"],
            email = customer_dataA["email"],
            phone = customer_dataA["phone"],
            role=UserRole.customer
        )
        user.hash_password(customer_dataA["password"])
        db.add(user)
        await db.commit()

    return user

@pytest.fixture
async def barber_userA(session_factory, barber_dataA):
    async with session_factory() as db:
        user = User(
            full_name = barber_dataA["full_name"],
            email = barber_dataA["email"],
            phone = barber_dataA["phone"],
            role=UserRole.barber
        )
        user.hash_password(barber_dataA["password"])
        db.add(user)
        await db.commit()

    return user

@pytest.fixture
async def customer_userB(session_factory, customer_dataB):
    async with session_factory() as db:
        user = User(
            full_name = customer_dataB["full_name"],
            email = customer_dataB["email"],
            phone = customer_dataB["phone"],
            role=UserRole.customer
        )
        user.hash_password(customer_dataB["password"])
        db.add(user)
        await db.commit()

    return user

@pytest.fixture
async def barber_userB(session_factory, barber_dataB):
    async with session_factory() as db:
        user = User(
            full_name = barber_dataB["full_name"],
            email = barber_dataB["email"],
            phone = barber_dataB["phone"],
            role=UserRole.barber
        )
        user.hash_password(barber_dataB["password"])
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

@pytest.fixture
async def sample_bookings(session_factory, customer_userA, customer_userB, barber_userA, barber_userB, sample_services):
    bookings = [
        Booking(
            id=1,
            customer_id=customer_userA.id,
            barber_id=barber_userA.id,
            booking_date=date.today(),
            start_time=time(9, 0),
            end_time=(datetime.combine(date.today(), time(9, 0)) + timedelta(minutes=float((sample_services[0].duration_minutes + sample_services[1].duration_minutes)))).time(),
            total_price=100000,
            status=BookingStatus.pending,
        ),
        Booking(
            id=2,
            customer_id=customer_userB.id,
            barber_id=barber_userB.id,
            booking_date=date.today(),
            start_time=time(10, 0),
            end_time=(datetime.combine(date.today(), time(10, 0)) + timedelta(minutes=float(sample_services[0].duration_minutes))).time(),
            total_price=100000,
            status=BookingStatus.pending,
        ),
        Booking(
            id=3,
            customer_id=customer_userB.id,
            barber_id=barber_userB.id,
            booking_date=date.today(),
            start_time=time(10, 0),
            end_time=time(10, 30),
            total_price=100000,
            status=BookingStatus.completed,
        ),
        Booking(
            id=4,
            customer_id=customer_userB.id,
            barber_id=barber_userB.id,
            booking_date=date.today(),
            start_time=time(10, 0),
            end_time=time(10, 30),
            total_price=100000,
            status=BookingStatus.confirmed,
        )
    ]

    async with session_factory() as db:
        db.add_all(bookings)
        await db.commit()
        for b in bookings:
            await db.refresh(b)

    return bookings

@pytest.fixture
async def sample_booking_services(session_factory, sample_bookings, sample_services):
    booking_services = [
        BookingService(
            booking_id=sample_bookings[0].id,
            service_id=sample_services[0].id,
            price_at_booking=sample_services[0].price,
        ),
        BookingService(
            booking_id=sample_bookings[0].id,
            service_id=sample_services[1].id,
            price_at_booking=sample_services[1].price,
        ),
        BookingService(
            booking_id=sample_bookings[1].id,
            service_id=sample_services[0].id,
            price_at_booking=sample_services[0].price,
        ),
    ]

    async with session_factory() as db:
        db.add_all(booking_services)
        await db.commit()
        for bs in booking_services:
            await db.refresh(bs)

@pytest.fixture
async def sample_barber_schedules(session_factory, barber_userA, barber_userB):
    
    schedules: list[BarberSchedule] = [] 
    # Baber A
    for day in range(7):
        schedules.append(
            BarberSchedule(
                barber_id=barber_userA.id,
                date_of_week=day,
                start_time=time(8, 0),
                end_time=time(18, 0),
            )
        )

    # Barber B
    for day in range(7):
        schedules.append(
            BarberSchedule(
                barber_id=barber_userB.id,
                date_of_week=day,
                start_time=time(13, 0),
                end_time=time(21, 0),
            )
        )

    async with session_factory() as db:
        db.add_all(schedules)
        await db.commit()
        for s in schedules:
            await db.refresh(s)

    return schedules
