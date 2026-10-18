from typing import Annotated
from fastapi import Depends
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import time

from app.core.exception import DomainException
from app.dependencies import get_current_active_user
from app.core.database import BarberSchedule, User, get_db
from app.routers import service_logger


class _BarberScheduleException(DomainException):
    pass

class BarberScheduleNotFoundException(_BarberScheduleException):
    """Raise this exception if the barber schedule in question does not exists."""
    pass

class UserNotAllowedToViewBarberScheduleException(_BarberScheduleException):
    """Raise this exception if the user is not allowed to access barber schedule."""
    pass


class BarberSchedulePolicy:
    @staticmethod
    def user_can_access_barber_schedule(user: Annotated[User, Depends(get_current_active_user)], barber_id: int):
        is_admin = user.is_admin()
        is_assigned_barber = user.is_barber() and user.id == barber_id
        if not (is_admin or is_assigned_barber):
            service_logger.warning(
                "Unauthorized request to barber schedule from user",
                extra={"user_id":user.id, "role": user.role}
            )
            raise UserNotAllowedToViewBarberScheduleException("You are not allowed to perform this action")
        
    

class BarberScheduleService:
    def __init__(self, *, db: AsyncSession):
        self.db = db

    async def get_filtered_barber_schedules(
        self,
        barber_id: int,
        *,
        page: int,
        limit: int,
        date_of_week: int | None = None,
        is_off: bool | None = None,
    ):
        query = select(BarberSchedule).where(BarberSchedule.barber_id == barber_id)

        if date_of_week is not None:
            query = query.where(BarberSchedule.date_of_week == date_of_week)
        if is_off is not None:
            query = query.where(BarberSchedule.is_off == is_off)

        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # if total == 0:
        #     raise BarberScheduleNotFoundException("Barber Schedule Not Found")

        offset = (page - 1) * limit
        paginated_query = (
            query.offset(offset).limit(limit).order_by(BarberSchedule.id.desc())
        )
        result = await self.db.scalars(paginated_query)
        items = result.all()

        return items, total

    async def create_barber_schedule(
        self,
        barber_id: int,
        *,
        date_of_week: int,
        start_time: time,
        end_time: time,
        is_off: bool = False,
    ):
        barber_schedule = BarberSchedule()
        barber_schedule.barber_id = barber_id
        barber_schedule.date_of_week = date_of_week
        barber_schedule.start_time = start_time
        barber_schedule.end_time = end_time
        barber_schedule.is_off = is_off

        self.db.add(barber_schedule)

        if barber_schedule.is_off is False:
            await self._set_other_schedules_off(barber_schedule)
        
        await self.db.commit()
        await self.db.refresh(barber_schedule)

        service_logger.info(
            "Barber schedule created successfully", 
            extra={"barber_id": barber_id, "barber_schedule_id": barber_schedule.id}
        )
        
        return barber_schedule

    async def _set_other_schedules_off(self, barber_schedule: BarberSchedule):
        await self.db.execute(
            update(BarberSchedule)
            .where(
                BarberSchedule.barber_id == barber_schedule.barber_id,
                BarberSchedule.date_of_week == barber_schedule.date_of_week,
                BarberSchedule.id != barber_schedule.id,
            )
            .values(is_off=True)
        )
    
    async def update_barber_schedule(
        self,
        barber_schedule_id: int,
        barber_id: int,
        *,
        date_of_week: int | None = None,
        start_time: time | None = None,
        end_time: time | None = None,
        is_off: bool | None = None,
    ):
        try:
            barber_schedule = await self.get_barber_schedule_by_id(barber_id=barber_id, barber_schedule_id=barber_schedule_id)
        except BarberScheduleNotFoundException as e:
            raise e

        if date_of_week is not None:
            barber_schedule.date_of_week = date_of_week
        if start_time is not None:
            barber_schedule.start_time = start_time
        if end_time is not None:
            barber_schedule.end_time = end_time
        if is_off is not None:
            barber_schedule.is_off = is_off

        if barber_schedule.is_off is False:
            await self._set_other_schedules_off(barber_schedule)

        await self.db.commit()
        await self.db.refresh(barber_schedule)

        service_logger.info(
            "Barber schedule updated successfully", 
            extra={"barber_id": barber_id, "barber_schedule_id": barber_schedule.id}
        )

        return barber_schedule
    
    async def delete_barber_schedule(
        self,
        barber_schedule_id: int,
        barber_id: int,
    ):
        try:
            barber_schedule = await self.get_barber_schedule_by_id(barber_id=barber_id, barber_schedule_id=barber_schedule_id)
        except BarberScheduleNotFoundException as e:
            raise e

        await self.db.delete(barber_schedule)
        await self.db.commit()

        service_logger.info(
            "Barber schedule deleted successfully", 
            extra={"barber_id": barber_id, "barber_schedule_id": barber_schedule.id}
        )

    async def get_barber_schedule_by_id(
        self, 
        barber_schedule_id: int,
        barber_id: int,
    ):
        barber_schedule = await self.db.scalar(
            select(BarberSchedule).where(
                BarberSchedule.id == barber_schedule_id,
                BarberSchedule.barber_id == barber_id,
            )
        )
        if not barber_schedule:
            service_logger.warning(
                "Barber schedule look up failed: barber schedule not found", 
                extra={"barber_id": barber_id, "barber_schedule_id": barber_schedule_id}
            )
            raise BarberScheduleNotFoundException("Barber schedule not found")

        return barber_schedule
        


async def get_barber_schedules_service(db: AsyncSession = Depends(get_db)):
    return BarberScheduleService(db=db)


BarberScheduleServiceDep = Annotated[
    BarberScheduleService, Depends(get_barber_schedules_service)
]
