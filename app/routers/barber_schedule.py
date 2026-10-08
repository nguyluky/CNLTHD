from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis_fastapi import CacheBackendDep
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import User, UserRole, get_db
from app.core.exception import NotFoundException
from app.dependencies import require_roles
from app.schemas.barber_schedule import (
    BarberScheduleCreateIn,
    BarberScheduleFilterParam,
    BarberScheduleOut,
    BarberScheduleUpdateIn,
)
from app.schemas.common import PageResponse, create_page_response
from app.services import barber_schedule_service, barber_service
from app.services.barber_schedule_service import (
    BarberScheduleServiceDep,
    BarberSchedulePolicy,
)

router = APIRouter(prefix="/barber_schedules", tags=["Barber Schedule"])


@router.get(
    "/{barber_id}/schedules",
    description="Get barber schedules for the current barber or admin",
    response_model=PageResponse[BarberScheduleOut],
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(require_roles(UserRole.admin, UserRole.barber)),
        Depends(BarberSchedulePolicy.user_can_access_barber_schedule),
    ],
)
async def get_barber_schedules(
    barber_id: int,
    filter: Annotated[BarberScheduleFilterParam, Query()],
    barber_schedule_service: BarberScheduleServiceDep,
):
    """
    Get barber schedules for the current barber or admin.
    """

    items, total = await barber_schedule_service.get_filtered_barber_schedules(
        barber_id,
        page=filter.page,
        limit=filter.limit,
        date_of_week=filter.date_of_week,
        is_off=filter.is_off,
    )

    return create_page_response(
        items=items,
        total=total,
        page=filter.page,
        size=filter.limit,
    )


@router.post(
    "/{barber_id}/schedules",
    description="Create a new barber schedule for the current barber or admin",
    response_model=BarberScheduleOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_roles(UserRole.admin, UserRole.barber)),
        Depends(BarberSchedulePolicy.user_can_access_barber_schedule),
    ],
)
async def create_barber_schedule(
    barber_id: int,
    body: BarberScheduleCreateIn,
    redis: CacheBackendDep,
    barber_schedule_service: BarberScheduleServiceDep,
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.barber)),
):
    """
    Create a new barber schedule for the current barber or admin.
    """

    barber_schedule = await barber_schedule_service.create_barber_schedule(
        barber_id,
        date_of_week=body.date_of_week,
        start_time=body.start_time,
        end_time=body.end_time,
        is_off=body.is_off,
    )

    await redis.delete_group("available_slot")

    return barber_schedule


@router.patch(
    "/{barber_id}/schedules/{schedule_id}",
    description=" Admins have the authority to edit barbers' schedules."
    "Barbers can edit their own schedules.",
    response_model=BarberScheduleOut,
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(require_roles(UserRole.admin, UserRole.barber)),
        Depends(BarberSchedulePolicy.user_can_access_barber_schedule),
    ],
)
async def update_barber_schedule(
    barber_id: int,
    schedule_id: int,
    body: BarberScheduleUpdateIn,
    redis: CacheBackendDep,
    barber_schedule_service: BarberScheduleServiceDep,
):
    """
    Admins have the authority to edit barbers' schedules.
    Barbers can edit their own schedules.
    """

    barber_schedule = await barber_schedule_service.update_barber_schedule(
        schedule_id,
        barber_id,
        date_of_week=body.date_of_week,
        start_time=body.start_time,
        end_time=body.end_time,
        is_off=body.is_off,
    )

    await redis.delete_group("available_slot")

    return barber_schedule


@router.delete(
    "/{barber_id}/schedules/{schedule_id}",
    description="Administrators have the authority to delete barbers' work schedules."
    "Barbers can delete their own work schedules.",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[
        Depends(require_roles(UserRole.admin, UserRole.barber)),
        Depends(BarberSchedulePolicy.user_can_access_barber_schedule),
    ],
)
async def delete_barber_schedule(
    barber_id: int,
    schedule_id: int,
    redis: CacheBackendDep,
    barber_schedule_service: BarberScheduleServiceDep,
):
    """
    Administrators have the authority to delete barbers' work schedules.
    Barbers can delete their own work schedules.
    """

    await barber_schedule_service.delete_barber_schedule(
        barber_schedule_id=schedule_id, barber_id=barber_id
    )

    await redis.delete_group("available_slot")
