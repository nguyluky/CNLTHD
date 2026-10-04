from datetime import time

import pytest
from sqlalchemy import select

from app.core.database import BarberSchedule


pytestmark = pytest.mark.anyio


def schedule_payload(
    date_of_week: int = 0,
    start_time: str = "09:00:00",
    end_time: str = "17:00:00",
    is_off: bool = False,
) -> dict:
    return {
        "date_of_week": date_of_week,
        "start_time": start_time,
        "end_time": end_time,
        "is_off": is_off,
    }


async def create_schedule(
    session_factory,
    barber_id: int,
    date_of_week: int = 0,
    start_time: time = time(9, 0),
    end_time: time = time(17, 0),
    is_off: bool = False,
) -> BarberSchedule:
    async with session_factory() as db:
        schedule = BarberSchedule(
            barber_id=barber_id,
            date_of_week=date_of_week,
            start_time=start_time,
            end_time=end_time,
            is_off=is_off,
        )
        db.add(schedule)
        await db.commit()
        await db.refresh(schedule)
        return schedule



async def test_get_barber_schedules_applies_filters(
    create_auth_client_for_user, barber_user, session_factory
):
    matching = await create_schedule(
        session_factory, barber_user.id, date_of_week=2, is_off=True
    )
    await create_schedule(
        session_factory, barber_user.id, date_of_week=3, is_off=False
    )
    barber_client = await create_auth_client_for_user(barber_user)

    response = await barber_client.get(
        f"/barber_schedules/{barber_user.id}/schedules",
        params={"date_of_week": 2, "is_off": "true"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [matching.id]


async def test_get_barber_schedules_forbidden_for_another_barber(
    create_auth_client_for_user, barber_user, admin_user
):
    barber_client = await create_auth_client_for_user(barber_user)

    response = await barber_client.get(
        f"/barber_schedules/{admin_user.id}/schedules"
    )

    assert response.status_code == 403


async def test_get_barber_schedules_not_found_when_empty(
    create_auth_client_for_user, barber_user
):
    barber_client = await create_auth_client_for_user(barber_user)

    response = await barber_client.get(
        f"/barber_schedules/{barber_user.id}/schedules"
    )

    assert response.status_code == 404
    assert response.json()["message"] == "Barber Schedule Not Found"


async def test_create_barber_schedule(
    create_auth_client_for_user, barber_user, session_factory
):
    barber_client = await create_auth_client_for_user(barber_user)
    payload = schedule_payload(date_of_week=3)

    response = await barber_client.post(
        f"/barber_schedules/{barber_user.id}/schedules", json=payload
    )

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "id": body["id"],
        "barber_id": barber_user.id,
        **payload,
    }
    async with session_factory() as db:
        saved = await db.scalar(
            select(BarberSchedule).where(BarberSchedule.id == body["id"])
        )
        assert saved is not None
        assert saved.date_of_week == payload["date_of_week"]


async def test_admin_can_create_schedule_for_barber(
    create_auth_client_for_user, admin_user, barber_user, session_factory
):
    admin_client = await create_auth_client_for_user(admin_user)
    payload = schedule_payload(date_of_week=5)

    response = await admin_client.post(
        f"/barber_schedules/{barber_user.id}/schedules",
        json=payload,
    )

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "id": body["id"],
        "barber_id": barber_user.id,
        **payload,
    }
    async with session_factory() as db:
        saved = await db.scalar(
            select(BarberSchedule).where(BarberSchedule.id == body["id"])
        )
        assert saved is not None
        assert saved.date_of_week == payload["date_of_week"]


async def test_customer_cannot_create_barber_schedule(
    create_auth_client_for_user, customer_user, barber_user
):
    customer_client = await create_auth_client_for_user(customer_user)

    response = await customer_client.post(
        f"/barber_schedules/{barber_user.id}/schedules",
        json=schedule_payload(),
    )

    assert response.status_code == 403


async def test_create_barber_schedule_rejects_invalid_day(
    create_auth_client_for_user, barber_user
):
    barber_client = await create_auth_client_for_user(barber_user)

    response = await barber_client.post(
        f"/barber_schedules/{barber_user.id}/schedules",
        json=schedule_payload(date_of_week=7),
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "VALIDATION_ERROR"


async def test_update_barber_schedule(
    create_auth_client_for_user, barber_user, session_factory
):
    schedule = await create_schedule(
        session_factory, barber_user.id, date_of_week=1, is_off=True
    )
    barber_client = await create_auth_client_for_user(barber_user)

    response = await barber_client.patch(
        f"/barber_schedules/{barber_user.id}/schedules/{schedule.id}",
        json={"date_of_week": 2, "start_time": "10:00:00"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == schedule.id
    assert body["date_of_week"] == 2
    assert body["start_time"] == "10:00:00"
    assert body["end_time"] == "17:00:00"
    assert body["is_off"] is True
    async with session_factory() as db:
        saved = await db.scalar(
            select(BarberSchedule).where(BarberSchedule.id == body["id"])
        )
        assert saved is not None
        assert saved.date_of_week == body["date_of_week"]
        assert saved.start_time.strftime("%H:%M:%S") == "10:00:00"


async def test_update_barber_schedule_not_found(
    create_auth_client_for_user, barber_user
):
    barber_client = await create_auth_client_for_user(barber_user)

    response = await barber_client.patch(
        f"/barber_schedules/{barber_user.id}/schedules/999",
        json={"is_off": True},
    )

    assert response.status_code == 404
    assert response.json()["message"] == "Barber schedule not found"


async def test_delete_barber_schedule(
    create_auth_client_for_user, barber_user, session_factory
):
    schedule = await create_schedule(session_factory, barber_user.id)
    barber_client = await create_auth_client_for_user(barber_user)

    response = await barber_client.delete(
        f"/barber_schedules/{barber_user.id}/schedules/{schedule.id}"
    )

    assert response.status_code == 204
    async with session_factory() as db:
        assert await db.scalar(
            select(BarberSchedule).where(BarberSchedule.id == schedule.id)
        ) is None


async def test_delete_barber_schedule_not_found(
    create_auth_client_for_user, barber_user
):
    barber_client = await create_auth_client_for_user(barber_user)

    response = await barber_client.delete(
        f"/barber_schedules/{barber_user.id}/schedules/999"
    )

    assert response.status_code == 404
    assert response.json()["message"] == "Barber schedule not found"