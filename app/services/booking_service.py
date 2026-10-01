from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from sqlalchemy.orm import selectinload
from app.core.database import Booking, User, get_db
from app.dependencies import get_current_active_user


async def get_booking_detail(
    booking_id: int,
    db: AsyncSession,
) -> Booking | None:
    booking = (await db.scalars(
        select(Booking).where(Booking.id == booking_id).options(selectinload(Booking.services))
    )).first()

    if not booking:
        return None

    return booking