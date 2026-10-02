
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import Booking, BookingService, BookingStatus, Service, User, get_db
from app.core.exception import NotFoundException


async def get_booking_by_id(
    booking_id: int,
    db: AsyncSession,
) -> Booking:
    booking = (await db.scalars(
        select(Booking).where(Booking.id == booking_id).options(selectinload(Booking.services))
    )).first()

    if not booking:
        raise NotFoundException("Booking detail not found")

    return booking

async def update_booking_status(
    booking: Booking,
    new_status: BookingStatus,
    db: AsyncSession,
):
    booking.status = new_status
    await db.commit()
    await db.refresh(booking)

async def update_booking_schedule(
    booking: Booking,
    update_data: dict,
    db: AsyncSession,
):
    booking_services = (await db.scalars(select(BookingService).where(BookingService.booking_id == booking.id))).all()

    total_duration = 0
    for bs in booking_services:
        service = (await db.scalars(select(Service).where(Service.id == bs.service_id))).first()
        if service:
            total_duration+=service.duration_minutes

    if "booking_date" in update_data:
        booking_date = update_data["booking_date"]
        booking.booking_date = booking_date

    if "start_time" in update_data:
        start_dt = datetime.combine(booking.booking_date, update_data["start_time"])
        end_dt = start_dt + timedelta(minutes=total_duration)
        end_time = end_dt.time()

        booking.start_time = update_data["start_time"]
        booking.end_time = end_time

    await db.commit()
    await db.refresh(booking)

    return booking