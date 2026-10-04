from datetime import datetime, time, timedelta
import math

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import (
    Booking,
    BookingService,
    BookingStatus,
    Service,
    User,
)
from app.core.exception import NotFoundException, RequestedServiceForBookingNotFound
from app.schemas.booking import BookingFilterParam


async def get_filtered_bookings_for_user(
    filter: BookingFilterParam,
    current_user: User,
    db: AsyncSession,
):
    query = select(Booking)

    # assign query based on user role
    if current_user.is_customer():
        query = query.where(Booking.customer_id == current_user.id)
    elif current_user.is_barber():
        query = query.where(Booking.barber_id == current_user.id)
    elif current_user.is_admin():
        if filter.customer_id:
            query = query.where(Booking.customer_id == filter.customer_id)
        if filter.barber_id:
            query = query.where(Booking.barber_id == filter.barber_id)

    # apply filter to query
    if filter.booking_date:
        query = query.where(Booking.booking_date == filter.booking_date)
    if filter.status:
        query = query.where(Booking.status == filter.status)

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    if total == 0:
        raise NotFoundException("Booking not found")

    # pagination
    offset = (filter.page - 1) * filter.limit
    paginated_query = (
        query.offset(offset).limit(filter.limit).order_by(Booking.created_at.desc())
    )

    result = await db.scalars(paginated_query)
    items = result.all()
    pages = math.ceil(total / filter.limit)

    return items, total, pages


async def get_booking_by_id(
    booking_id: int,
    db: AsyncSession,
) -> Booking:
    booking = (
        await db.scalars(
            select(Booking)
            .where(Booking.id == booking_id)
            .options(selectinload(Booking.services))
        )
    ).first()

    if not booking:
        raise NotFoundException("Booking detail not found")

    return booking


async def create_booking(
    current_user: User,
    body: dict,
    db: AsyncSession,
) -> Booking:
    service_result = await db.scalars(
        select(Service).where(Service.id.in_(body["service_ids"]))
    )

    services = service_result.all()
    if len(services) != len(body["service_ids"]):
        raise RequestedServiceForBookingNotFound("One of the services does not exist")

    total_price = sum(s.price for s in services)
    total_duration = sum(s.duration_minutes for s in services)

    start_dt = datetime.combine(body["booking_date"], body["start_time"])
    end_dt = start_dt + timedelta(minutes=total_duration)
    end_time = end_dt.time()

    # create a copy that excludes "service_ids"
    body_excluded = {k: v for k, v in body.items() if k not in {"service_ids"}}

    booking = Booking(
        customer_id=current_user.id,
        **body_excluded,
        end_time=end_time,
        total_price=total_price,
        status=BookingStatus.pending,
    )

    db.add(booking)
    await db.flush()

    # create booking_services
    for service in services:
        booking_service = BookingService(
            booking_id=booking.id, service_id=service.id, price_at_booking=service.price
        )
        db.add(booking_service)

    await db.commit()

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
    booking_services = (
        await db.scalars(
            select(BookingService).where(BookingService.booking_id == booking.id)
        )
    ).all()

    total_duration = 0
    for bs in booking_services:
        service = (
            await db.scalars(select(Service).where(Service.id == bs.service_id))
        ).first()
        if service:
            total_duration += service.duration_minutes

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
