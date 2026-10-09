import pytest
from datetime import date, time, timedelta, datetime
from app.core.database import User, UserRole
from app.schemas.barber import *
from app.services.barber_service import get_barbers_cache_key

from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.anyio


async def test_get_barbers_returns_barbers_with_pagination_metadata(
    client, barber_userA, customer_userA
):
    response = await client.get("/barbers")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "items": [
            {
                "id": barber_userA.id,
                "full_name": barber_userA.full_name,
                "email": barber_userA.email,
                "phone": barber_userA.phone,
                "is_active": True,
                "role": "barber",
            }
        ],
        "total": 1,
        "page": 1,
        "size": 10,
        "pages": 1,
    }
    assert body["items"][0]["id"] != customer_userA.id


@pytest.mark.parametrize(
    "filter_params",
    [
        {"full_name": "Test bar"},
        {"email": "barbera@example"},
        {"phone": "090123478"},
        {"is_active": "true"},
    ],
)
async def test_get_barbers_applies_filters(client, barber_userA, filter_params):
    response = await client.get("/barbers", params=filter_params)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [barber["id"] for barber in body["items"]] == [barber_userA.id]


async def test_get_barbers_paginates_results(client, session_factory, barber_userA):
    async with session_factory() as db:
        aaron = User(
            full_name="Aaron Barber",
            email="aaron@example.com",
            phone="0900000001",
            hashed_password="unused",
            role=UserRole.barber,
            is_active=True,
        )
        zoe = User(
            full_name="Zoe Barber",
            email="zoe@example.com",
            phone="0900000003",
            hashed_password="unused",
            role=UserRole.barber,
            is_active=False,
        )
        db.add_all([aaron, zoe])
        await db.commit()

    response = await client.get("/barbers", params={"page": 2, "limit": 2})

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": zoe.id,
                "full_name": zoe.full_name,
                "email": zoe.email,
                "phone": zoe.phone,
                "is_active": zoe.is_active,
                "role": "barber",
            }
        ],
        "total": 3,
        "page": 2,
        "size": 2,
        "pages": 2,
    }


async def test_get_barber_by_id(client, barber_userA):
    response = await client.get(f"/barbers/{barber_userA.id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": barber_userA.id,
        "full_name": barber_userA.full_name,
        "email": barber_userA.email,
        "phone": barber_userA.phone,
        "is_active": True,
        "role": "barber",
    }


@pytest.mark.parametrize("missing_or_non_barber_id", [0, 999])
async def test_get_barber_by_id_not_found(client, missing_or_non_barber_id):
    response = await client.get(f"/barbers/{missing_or_non_barber_id}")

    assert response.status_code == 404
    assert response.json() == {
        'error_code': 'BARBER_NOT_FOUND_EXCEPTION',
        "message": "Barber not found",
    }


async def test_get_barber_by_id_does_not_return_other_roles(client, customer_userA):
    response = await client.get(f"/barbers/{customer_userA.id}")

    assert response.status_code == 404
    assert response.json()["message"] == "Barber not found"


async def test_get_available_slots_successfully(
    client,
    barber_userA,
    sample_barber_schedules
):
    target_date = date.today()
    schedule = sample_barber_schedules[0]
    start_time_str = str(schedule.start_time)
    end_time_str = str((datetime.combine(date.today(), schedule.start_time) + timedelta(minutes=30)).time())

    response = await client.get(
        f"barbers/{barber_userA.id}/available-slots", 
        params={"booking_date": target_date.isoformat(), "slot_duration": 30}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["available_slots"]) > 0
    assert data["available_slots"][0]["start_time"] == start_time_str
    assert data["available_slots"][0]["end_time"] == end_time_str

async def test_available_slots_caching_and_invalidation_on_booking_created(
    client, 
    redis_client, 
    cache, 
    barber_userA, 
    sample_barber_schedules,
    sample_services,
    create_auth_client_for_user,
    customer_userA
):
    target_date = date.today()

    # get cache
    response = await client.get(
        f"barbers/{barber_userA.id}/available-slots", 
        params={"booking_date": target_date.isoformat(), "slot_duration": 30}
    )
    assert response.status_code == 200

    cache_pattern = f"*barber:{barber_userA.id}:available_slots:{target_date.isoformat()}:*"
    all_keys = await redis_client.keys(cache_pattern)
    print("ACTUAL REDIS KEYS:", all_keys)
    assert len(all_keys) == 1

    booking_payload = {
        "barber_id": barber_userA.id,
        "booking_date": target_date.isoformat(),
        "start_time": "14:00:00",
        "service_ids": [sample_services[0].id],
    }

    customer_client = await create_auth_client_for_user(customer_userA)
    response = await customer_client.post("/bookings", json=booking_payload)
    assert response.status_code == 201

    assert len(await redis_client.keys(cache_pattern)) == 0, "cache should be invalidate after a booking creation"




async def test_cache_invalidation_on_schedule_change(
    client, 
    redis_client, 
    cache, 
    barber_userA, 
    sample_barber_schedules,
    create_auth_client_for_user,
):
    target_date = date.today()
    day_of_week = target_date.weekday()

    # get cache
    response = await client.get(
        f"barbers/{barber_userA.id}/available-slots", 
        params={"booking_date": target_date.isoformat(), "slot_duration": 30}
    )
    assert response.status_code == 200

    cache_pattern = f"*barber:{barber_userA.id}:available_slots:*"
    all_keys = await redis_client.keys(cache_pattern)
    print("ACTUAL REDIS KEYS:", all_keys)
    assert len(all_keys) > 0

    # update barberA schedule
    barber_client = await create_auth_client_for_user(barber_userA)
    schedule = sample_barber_schedules[0]
    update_payload = {
        "date_of_week": day_of_week, 
        "start_time": "10:00:00"
    }
    
    update_response = await barber_client.patch(
        f"/barber_schedules/{barber_userA.id}/schedules/{schedule.id}",
        json=update_payload,
    )

    assert update_response.status_code == 200, "update should succeeded"

    assert len(await redis_client.keys(cache_pattern)) == 0, "cache should be invalidate after a schedule update"


async def test_get_barbers_cache(
    client,
    cache,
    barber_userA,
    barber_userB,
):
    
    filter_params = BarberFilterParam(
        page=1,
        limit=10
    )

    key = get_barbers_cache_key(filter_params)

    assert await cache.get(
        key,
        eviction_group="barber"
    ) is None

    response = await client.get(
        "/barbers",
        params={
            "page": 1,
            "limit": 10
        }
    )

    assert response.status_code == 200

    cached = await cache.get(
        key,
        eviction_group="barber"
    )

    assert cached is not None
    assert cached == response.json()

    assert cached["total"] == 2
    assert len(cached["items"]) == 2
    assert cached["page"] == 1
    assert cached["size"] == 10

async def test_get_barber_cache(
    client,
    cache,
    barber_userA,
):
    barber_id = barber_userA.id
    key = f"barbers:detail:{barber_id}"

    assert await cache.get(
        key,
        eviction_group="barber"
    ) is None

    response = await client.get(
        f"/barbers/{barber_id}"
    )

    assert response.status_code == 200

    cached = await cache.get(
        key,
        eviction_group="barber"
    )

    assert cached is not None
    assert cached == response.json()