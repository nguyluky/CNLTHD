from datetime import date, datetime, time, timedelta
import pytest
from sqlalchemy import select
from app.core.database import Booking, BookingService, BookingStatus, Service
from app.services import booking_service

pytestmark = pytest.mark.anyio


@pytest.fixture
def booking_data():
    return {
        "barber_id": 1,
        "booking_date": str(date.today() + timedelta(days=1)),
        "start_time": "14:00:00",
        "service_ids": [1],
    }

# def booking_single(customer_user, barber_user):
#     return Booking(
#         id=1,
#         customer_id=customer_user.id,
#         barber_id=barber_user.id,
#         booking_date=date.today(),
#         start_time=time(9, 0),
#         end_time=time(9, 30),
#         total_price=100000,
#         status=BookingStatus.pending,
#     )


async def test_create_booking_success(
    create_auth_client_for_user, customer_userA, sample_services, booking_data
):
    customer_client = await create_auth_client_for_user(customer_userA)
    response = await customer_client.post("/bookings", json=booking_data)
    assert response.status_code == 201
    data = response.json()
    assert data["customer_id"] == customer_userA.id
    assert data["start_time"] == booking_data["start_time"]
    assert data["end_time"] == "14:30:00"


async def test_create_booking_fail_with_bad_request(
    create_auth_client_for_user, customer_userA, sample_services
):
    payload = {
        "barber_id": 1,
        "booking_date": str(date.today() + timedelta(days=1)),
        "start_time": "14:00:00",
        "service_ids": [0],
    }
    customer_client = await create_auth_client_for_user(customer_userA)
    response = await customer_client.post("/bookings", json=payload)
    assert response.status_code == 400


async def test_create_booking_fail_with_forbidden(
    create_auth_client_for_user, admin_user, sample_services, booking_data
):
    admin_client = await create_auth_client_for_user(admin_user)
    response = await admin_client.post("/bookings", json=booking_data)
    assert response.status_code == 403


async def test_get_bookings_with_customer(
    create_auth_client_for_user, customer_userA, sample_bookings
):
    customer_client = await create_auth_client_for_user(customer_userA)
    response = await customer_client.get("/bookings?page=1&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["customer_id"] == customer_userA.id


async def test_get_bookings_with_barber(
    create_auth_client_for_user, barber_userA, sample_bookings
):
    barber_client = await create_auth_client_for_user(barber_userA)
    response = await barber_client.get("/bookings?page=1&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["barber_id"] == barber_userA.id


async def test_get_bookings_with_admin(
    create_auth_client_for_user, admin_user, sample_bookings
):
    admin_client = await create_auth_client_for_user(admin_user)
    response = await admin_client.get("/bookings?page=1&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == len(sample_bookings)


async def test_get_booking_detail_with_owner_customer(
    create_auth_client_for_user, session_factory, sample_bookings, customer_userA
):
    booking = sample_bookings[0]

    customer_client = await create_auth_client_for_user(customer_userA)
    response = await customer_client.get(f"/bookings/{booking.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == customer_userA.id


async def test_cancel_booking_with_owner_customer(
    create_auth_client_for_user, customer_userA, sample_bookings, session_factory
):
    booking = sample_bookings[0]

    customer_client = await create_auth_client_for_user(customer_userA)
    response = await customer_client.patch(f"/bookings/{booking.id}/cancel")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Cancel Booking successfully"

    # making sure the status actually changed
    async with session_factory() as db:
        result = (
            await db.scalars(select(Booking).where(Booking.id == booking.id))
        ).first()
        assert result.status == BookingStatus.cancelled


async def test_cancel_booking_fail_bad_request(
    create_auth_client_for_user, customer_userB, sample_bookings, session_factory
):
    booking = sample_bookings[2]

    customer_client = await create_auth_client_for_user(customer_userB)
    response = await customer_client.patch(f"/bookings/{booking.id}/cancel")
    assert response.status_code == 400

    # making sure the status stays the same
    async with session_factory() as db:
        result = (
            await db.scalars(select(Booking).where(Booking.id == booking.id))
        ).first()
        assert result.status == BookingStatus.completed


async def test_update_status_booking_with_admin(
    create_auth_client_for_user, admin_user, sample_bookings, session_factory
):
    booking = sample_bookings[0]
    booking.status = BookingStatus.completed

    payload = {"status": BookingStatus.confirmed}
    admin_client = await create_auth_client_for_user(admin_user)
    response = await admin_client.patch(f"/bookings/{booking.id}/status", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == BookingStatus.confirmed

    # making sure the status actually changed
    async with session_factory() as db:
        result = (
            await db.scalars(select(Booking).where(Booking.id == booking.id))
        ).first()
        assert result.status == BookingStatus.confirmed


async def test_reschedule_booking_with_owner_customer(
    create_auth_client_for_user,
    customer_userA,
    session_factory,
    sample_booking_services,
    sample_bookings
):
    booking = sample_bookings[0]

    payload = {
        "start_time": "17:00:00",
    }

    customer_client = await create_auth_client_for_user(customer_userA)
    response = await customer_client.patch(
        f"/bookings/{booking.id}/reschedule", json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Reschedule Booking successfully"

    # making sure the time actually changed
    async with session_factory() as db:
        result =await db.scalar(select(Booking).where(Booking.id == booking.id))
        
        assert str(result.start_time) == "17:00:00"
        assert str(result.end_time) == "18:15:00"


async def test_reschedule_booking_fail_with_not_found(
    create_auth_client_for_user, customer_userA, sample_bookings, session_factory
):
    booking = sample_bookings[0]

    payload = {
        "start_time": "17:00:00",
    }

    customer_client = await create_auth_client_for_user(customer_userA)
    response = await customer_client.patch(f"/bookings/{9999}/reschedule", json=payload)
    assert response.status_code == 404

    # making sure the schedule stays the same
    async with session_factory() as db:
        result = (
            await db.scalars(select(Booking).where(Booking.id == booking.id))
        ).first()
        assert str(result.start_time) == str(booking.start_time)
        assert str(result.end_time) == str(booking.end_time)


async def test_reschedule_booking_fail_with_forbidden(
    create_auth_client_for_user, sample_bookings, barber_userA, session_factory
):
    booking = sample_bookings[0]

    payload = {
        "start_time": "17:00:00",
    }

    barber_client = await create_auth_client_for_user(barber_userA)
    response = await barber_client.patch(
        f"/bookings/{booking.id}/reschedule", json=payload
    )
    assert response.status_code == 403

    # making sure the schedule stays the same
    async with session_factory() as db:
        result = (
            await db.scalars(select(Booking).where(Booking.id == booking.id))
        ).first()
        assert str(result.start_time) == str(booking.start_time)
        assert str(result.end_time) == str(booking.end_time)
