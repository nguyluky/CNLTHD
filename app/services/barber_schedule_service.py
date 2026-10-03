import math
from datetime import datetime, time, timedelta

from sqlalchemy.exc import SQLAlchemyError
from app.schemas.barber_schedule import BarberScheduleFilterParam
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import BarberSchedule
from app.core.exception import NotFoundException

async def get_filtered_barber_schedules(
        barber_id: int,
        filter: BarberScheduleFilterParam,
        db: AsyncSession,
):
    query = select(BarberSchedule).where(BarberSchedule.barber_id == barber_id)

    # apply filter to query
    if filter.date_of_week is not None:
        query = query.where(BarberSchedule.date_of_week == filter.date_of_week)
    if filter.is_off is not None:
        query = query.where(BarberSchedule.is_off == filter.is_off)

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    if total == 0:
        raise NotFoundException("Barber Schedule Not Found")

    # pagination
    offset = (filter.page - 1) * filter.limit
    paginated_query = (
        query.offset(offset).limit(filter.limit).order_by(BarberSchedule.id.desc())
    )

    result = await db.scalars(paginated_query)
    items = result.all()
    pages = math.ceil(total / filter.limit)

    return items, total, pages


async def create_barber_schedule(
    barber_id: int,
    body: dict,
    db: AsyncSession,
) -> BarberSchedule:
    
    barber_schedule = BarberSchedule(
        barber_id=barber_id,
        **body
    )
    db.add(barber_schedule)

    if barber_schedule.is_off is False:
        await set_other_schedules_off(
            barber_schedule=barber_schedule,
            db=db
        )

    await db.commit()
    await db.refresh(barber_schedule)
    
    return barber_schedule

async def set_other_schedules_off(
    barber_schedule: BarberSchedule,
    db: AsyncSession
):
    await db.execute(
        update(BarberSchedule)
        .where(
            BarberSchedule.barber_id == barber_schedule.barber_id,
            BarberSchedule.date_of_week == barber_schedule.date_of_week,
            BarberSchedule.id != barber_schedule.id
        )
        .values(is_off=True)
    )

async def update_barber_schedule(
    barber_schedule_id: int,
    barber_id: int,
    body: dict,
    db: AsyncSession,
):
    barber_schedule = await db.scalar(select(BarberSchedule).where(BarberSchedule.id == barber_schedule_id, BarberSchedule.barber_id == barber_id))
    if not barber_schedule:
        raise NotFoundException("Barber schedule not found")
    
    for key, value in body.items():
        setattr(barber_schedule, key, value)

    if barber_schedule.is_off is False:
        await set_other_schedules_off(
            barber_schedule=barber_schedule,
            db=db
        )
    
    await db.commit()
    await db.refresh(barber_schedule)
    
    return barber_schedule

async def delete_barber_schedule(
    barber_schedule_id: int,
    barber_id: int,
    db: AsyncSession,
):
    barber_schedule = await db.scalar(select(BarberSchedule).where(BarberSchedule.id == barber_schedule_id, BarberSchedule.barber_id == barber_id))
    if not barber_schedule:
        raise NotFoundException("Barber schedule not found")
    
    try:
        await db.delete(barber_schedule)
        await db.commit()
    except SQLAlchemyError as e:
        await db.rollback()
        raise e

    