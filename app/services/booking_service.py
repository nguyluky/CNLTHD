
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import Booking, BookingStatus, User, get_db
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

    return booking