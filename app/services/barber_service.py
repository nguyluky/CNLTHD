from datetime import datetime, time, timedelta
import math

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import User, UserRole

from app.core.exception import NotFoundException
from app.schemas.barber import BarberFilterParam

async def get_barbers(
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
        query.offset(offset).limit(filter.limit).order_by(User.full_name.desc())
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