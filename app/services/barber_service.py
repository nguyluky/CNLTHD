import math
from datetime import date, datetime, timedelta
import math
from redis_fastapi import CacheBackend
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import BarberSchedule, Booking, BookingStatus, User, UserRole

from app.core.exception import NotFoundException
from app.schemas.barber import BarberFilterParam
from redis_fastapi import CacheBackend

BUFFER_MINUTES = 10
DEFAULT_SLOT_DURATION = 30

async def get_filtered_barbers(
        filter: BarberFilterParam,
        db: AsyncSession
):
    query = select(User).where(User.role == UserRole.barber)

    if filter.full_name:
        query = query.where(User.full_name.contains(filter.full_name))
    if filter.email:
        query = query.where(User.email.contains(filter.email))
    if filter.phone:
        query = query.where(User.phone.contains(filter.phone))
    if filter.is_active is not None:
        query = query.where(User.is_active == filter.is_active)

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    if total == 0:
        raise NotFoundException("Service not found")

    # pagination
    offset = (filter.page - 1) * filter.limit
    paginated_query = (
        query.order_by(User.full_name.asc())
        .offset(offset)
        .limit(filter.limit)
    )

    result = await db.scalars(paginated_query)
    items = result.all()
    pages = math.ceil(total / filter.limit)

    return items, total, pages

async def get_barber_by_id(
        barber_id: int,
        db: AsyncSession
):
    barber = (await db.scalar(select(User).where(User.id == barber_id, User.role == UserRole.barber)))

    if not barber:
        raise NotFoundException("Barber not found")
    return barber

async def get_available_slot_minutes(
    barber_id: int,
    target_date: date,
    db: AsyncSession,
    slot_duration: int = DEFAULT_SLOT_DURATION,
):
    date_of_week = target_date.weekday()
    schedules = (await db.scalars(
        select(BarberSchedule)
        .where(
            BarberSchedule.barber_id == barber_id, 
            BarberSchedule.date_of_week == date_of_week, 
            BarberSchedule.is_off == False
        )
    )).all()

    if not schedules:
        return []

    existing_bookings = (await db.scalars(
        select(Booking)
        .where(
            Booking.barber_id == barber_id,
            Booking.status.in_([BookingStatus.pending, BookingStatus.confirmed]),
            Booking.booking_date == target_date
        )
    )).all()

    busy_intervals = []
    for b in existing_bookings:
        b_start = datetime.combine(target_date, b.start_time)
        b_end = datetime.combine(target_date, b.end_time) + timedelta(minutes=BUFFER_MINUTES)
        busy_intervals.append((b_start, b_end))

    available_slots = []
    for sche in schedules:
        curr_time = datetime.combine(target_date, sche.start_time)
        sche_end = datetime.combine(target_date, sche.end_time)

        while curr_time + timedelta(minutes=slot_duration) <= sche_end:
            slot_end = curr_time + timedelta(minutes=slot_duration)

            is_overlapping = any(
                max(curr_time, busy_start) < min(slot_end, busy_end)
                for busy_start, busy_end in busy_intervals
            )

            if not is_overlapping:
                available_slots.append({
                    "start_time": curr_time.strftime("%H:%M"),
                    "end_time": slot_end.strftime("%H:%M")
                })

            curr_time += timedelta(minutes=slot_duration)

    return available_slots   