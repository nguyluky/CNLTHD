from datetime import date, datetime, time, timedelta
import pytest
from sqlalchemy import select
from app.core.database import Booking, BookingService, BookingStatus, Service

pytestmark = pytest.mark.anyio

@pytest.fixture
async def sample_service(session_factory) -> Service:
    service = Service(id=1, name="Cắt tóc nam", price=100000, duration_minutes=30, is_active=True)
    async with session_factory() as db:
        db.add(service)
        await db.commit()
    return service

@pytest.fixture
def booking_data():
    return {
        "barber_id": 1,
        "booking_date": str(date.today() + timedelta(days=1)),
        "start_time": "14:00:00",
        "service_ids": [1]
    }


def booking_list(customer_user1, customer_user2, barber_user1, barber_user2):
    b1 = Booking(id=1, customer_id=customer_user1.id, barber_id=barber_user1.id, booking_date=date.today(), start_time=time(9,0), end_time=time(9,30), total_price=100000, status=BookingStatus.pending)
    b2 = Booking(id=2, customer_id=customer_user2.id, barber_id=barber_user2.id, booking_date=date.today(), start_time=time(10,0), end_time=time(10,30), total_price=100000, status=BookingStatus.pending)

    return [b1, b2]
def booking_single(customer_user, barber_user):
    return Booking(id=1, customer_id=customer_user.id, barber_id=barber_user.id, booking_date=date.today(), start_time=time(9,0), end_time=time(9,30), total_price=100000, status=BookingStatus.pending)

async def test_create_booking_success(create_auth_client_for_user, customer_user, sample_service, booking_data):
    customer_client = await create_auth_client_for_user(customer_user)
    response = await customer_client.post("/bookings", json=booking_data)
    assert response.status_code == 201
    data = response.json()
    assert data["customer_id"] == customer_user.id
    assert data["start_time"] == booking_data["start_time"]
    assert data["end_time"] == "14:30:00"

async def test_create_booking_fail_with_bad_request(create_auth_client_for_user, customer_user, sample_service):
    payload = {
        "barber_id": 1,
        "booking_date": str(date.today() + timedelta(days=1)),
        "start_time": "14:00:00",
        "service_ids": [2]
    }
    customer_client = await create_auth_client_for_user(customer_user)
    response = await customer_client.post("/bookings", json=payload)
    assert response.status_code == 400

async def test_create_booking_fail_with_forbidden(create_auth_client_for_user, admin_user, sample_service, booking_data):
    admin_client = await create_auth_client_for_user(admin_user)
    response = await admin_client.post("/bookings", json=booking_data)
    assert response.status_code == 403

async def test_get_bookings_with_customer(
    create_auth_client_for_user, customer_user, barber_user, admin_user, session_factory
):
    
    async with session_factory() as db:
        db.add_all(booking_list(customer_user, admin_user, barber_user, admin_user))
        await db.commit()

    customer_client = await create_auth_client_for_user(customer_user)
    response = await customer_client.get("/bookings?page=1&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["customer_id"] == customer_user.id

async def test_get_bookings_with_barber(
    create_auth_client_for_user, customer_user, barber_user, admin_user, session_factory
):
    
    async with session_factory() as db:
        db.add_all(booking_list(customer_user, admin_user, barber_user, admin_user))
        await db.commit()

    barber_client = await create_auth_client_for_user(barber_user)
    response = await barber_client.get("/bookings?page=1&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["barber_id"] == barber_user.id

async def test_get_bookings_with_admin(
    create_auth_client_for_user, customer_user, barber_user, admin_user, session_factory
):
    
    async with session_factory() as db:
        db.add_all(booking_list(customer_user, admin_user, barber_user, admin_user))
        await db.commit()

    admin_client = await create_auth_client_for_user(admin_user)
    response = await admin_client.get("/bookings?page=1&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2

async def test_get_booking_detail_with_owner_customer(
    create_auth_client_for_user, customer_user, barber_user, session_factory
):
    booking = booking_single(customer_user, barber_user)
    async with session_factory() as db:
        db.add(booking)
        await db.commit()

    customer_client = await create_auth_client_for_user(customer_user)
    response = await customer_client.get(f"/bookings/{booking.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == customer_user.id


async def test_cancel_booking_with_owner_customer(
    create_auth_client_for_user, customer_user, barber_user, session_factory
):
    booking = booking_single(customer_user, barber_user)
    async with session_factory() as db:
        db.add(booking)
        await db.commit()

    customer_client = await create_auth_client_for_user(customer_user)
    response = await customer_client.patch(f"/bookings/{booking.id}/cancel")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Cancel Booking successfully"

    # making sure the status actually changed
    async with session_factory() as db:
        result = (await db.scalars(select(Booking).where(Booking.id == booking.id))).first()
        assert result.status == BookingStatus.cancelled

async def test_cancel_booking_fail_bad_request(
    create_auth_client_for_user, customer_user, barber_user, session_factory
):
    booking = Booking(id=1, customer_id=customer_user.id, barber_id=barber_user.id, booking_date=date.today(), start_time=time(9,0), end_time=time(9,30), total_price=100000, status=BookingStatus.completed)
    async with session_factory() as db:
        db.add(booking)
        await db.commit()

    customer_client = await create_auth_client_for_user(customer_user)
    response = await customer_client.patch(f"/bookings/{booking.id}/cancel")
    assert response.status_code == 400

    # making sure the status stays the same
    async with session_factory() as db:
        result = (await db.scalars(select(Booking).where(Booking.id == booking.id))).first()
        assert result.status == BookingStatus.completed

async def test_update_status_booking_with_admin(
    create_auth_client_for_user, admin_user, barber_user, session_factory
):
    booking = Booking(id=1, customer_id=20, barber_id=barber_user.id, booking_date=date.today(), start_time=time(9,0), end_time=time(9,30), total_price=100000, status=BookingStatus.pending)
    async with session_factory() as db:
        db.add(booking)
        await db.commit()

    payload = {
        "status": BookingStatus.confirmed
    }
    admin_client = await create_auth_client_for_user(admin_user)
    response = await admin_client.patch(f"/bookings/{booking.id}/status", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Update Booking status successfully"

    # making sure the status actually changed
    async with session_factory() as db:
        result = (await db.scalars(select(Booking).where(Booking.id == booking.id))).first()
        assert result.status == BookingStatus.confirmed

async def test_reschedule_booking_with_owner_customer(
    create_auth_client_for_user, customer_user, barber_user, session_factory, sample_service
):
    booking = booking_single(customer_user, barber_user)
    booking_service = BookingService(id=1, booking_id=booking.id, service_id=sample_service.id, price_at_booking=sample_service.price)
    async with session_factory() as db:
        db.add_all([booking, booking_service])
        await db.commit()

    payload = {
        "start_time": "17:00:00",
    }

    customer_client = await create_auth_client_for_user(customer_user)
    response = await customer_client.patch(f"/bookings/{booking.id}/reschedule", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Reschedule Booking successfully"

    # making sure the time actually changed
    async with session_factory() as db:
        result = (await db.scalars(select(Booking).where(Booking.id == booking.id))).first()
        assert str(result.start_time) ==  "17:00:00"
        assert str(result.end_time) == "17:30:00"

async def test_reschedule_booking_fail_with_not_found(
    create_auth_client_for_user, customer_user, barber_user, session_factory
):
    booking = booking_single(customer_user, barber_user)
    async with session_factory() as db:
        db.add(booking)
        await db.commit()

    payload = {
        "start_time": "17:00:00",
    }

    customer_client = await create_auth_client_for_user(customer_user)
    response = await customer_client.patch(f"/bookings/{2}/reschedule", json=payload)
    assert response.status_code == 404

    # making sure the schedule stays the same
    async with session_factory() as db:
        result = (await db.scalars(select(Booking).where(Booking.id == booking.id))).first()
        assert str(result.start_time) ==  str(booking.start_time)
        assert str(result.end_time) == str(booking.end_time)

async def test_reschedule_booking_fail_with_forbidden(
    create_auth_client_for_user, customer_user, barber_user, session_factory
):
    booking = booking_single(customer_user, barber_user)
    async with session_factory() as db:
        db.add(booking)
        await db.commit()

    payload = {
        "start_time": "17:00:00",
    }

    barber_client = await create_auth_client_for_user(barber_user)
    response = await barber_client.patch(f"/bookings/{booking.id}/reschedule", json=payload)
    assert response.status_code == 403

    # making sure the schedule stays the same
    async with session_factory() as db:
        result = (await db.scalars(select(Booking).where(Booking.id == booking.id))).first()
        assert str(result.start_time) ==  str(booking.start_time)
        assert str(result.end_time) == str(booking.end_time)


    

