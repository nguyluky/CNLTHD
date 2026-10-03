from sqlalchemy.exc import SQLAlchemyError

from app.schemas.barber_schedule import BarberScheduleFilter, BarberScheduleResponse, BarberScheduleCreate, BarberScheduleUpdate
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import BarberSchedule, User, UserRole
from app.core.exception import NotFoundException

# async def get_filtered_barber_schedules(
#     filter: BarberScheduleFilter,
#     barber_id: int,
#     db: AsyncSession,
# ):
#     query = select(BarberSchedule).where(BarberSchedule.barber_id == barber_id)

#     # apply filter to query
#     if filter.date_of_week is not None:
#         query = query.where(BarberSchedule.date_of_week == filter.date_of_week)
#     if filter.is_off is not None:
#         query = query.where(BarberSchedule.is_off == filter.is_off)

#     count_query = select(func.count()).select_from(query.subquery())
#     total = await db.scalar(count_query) or 0

#     if total == 0:
#         raise NotFoundException("Barber schedule not found")

#     # pagination
#     offset = (filter.page - 1) * filter.limit
#     paginated_query = (
#         query.offset(offset).limit(filter.limit).order_by(BarberSchedule.date_of_week.asc())
#     )

#     result = await db.scalars(paginated_query)
#     items = result.all()
#     pages = (total + filter.limit - 1) // filter.limit

#     return items, total, pages


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
    await db.commit()
    await db.refresh(barber_schedule)
    
    return barber_schedule

async def update_barber_schedule(
    barber_schedule_id: int,
    barber_id: int,
    body: dict,
    db: AsyncSession,
):
    barber_schedule = await db.get(BarberSchedule, barber_schedule_id)
    if not barber_schedule:
        raise NotFoundException("Barber schedule not found")
    
    for key, value in body.items():
        setattr(barber_schedule, key, value)
    
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

    