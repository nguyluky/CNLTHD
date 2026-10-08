from redis_fastapi import CacheBackendDep
from sqlalchemy.exc import SQLAlchemyError
from typing import Annotated
from app.core.exception import NotFoundException
from app.core.database import UserRole, get_db, User
from app.schemas.barber_schedule import BarberScheduleFilterParam, BarberScheduleOut, BarberScheduleCreateIn, BarberScheduleUpdateIn
from app.dependencies import require_roles
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.services import barber_service, barber_schedule_service
from app.schemas.common import PageResponse

router = APIRouter(prefix="/barber_schedules", tags=["Barber Schedule"])

@router.get(
    "/{barber_id}/schedules",
    description="Get barber schedules for the current barber or admin",
    response_model=PageResponse[BarberScheduleOut],
    status_code=status.HTTP_200_OK,
)
async def get_barber_schedules(
    barber_id: int,
    filter: Annotated[BarberScheduleFilterParam, Query()],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.barber))
    ):
    """
    Get barber schedules for the current barber or admin.
    """

    is_admin = current_user.is_admin()
    is_assigned_barber = (
            current_user.is_barber() and current_user.id == barber_id
        )
    if not (is_admin or is_assigned_barber):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allow to perform this action",
        )

    try:
        items, total, pages = await barber_schedule_service.get_filtered_barber_schedules(barber_id, filter=filter, db=db)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    validated_items = [
        BarberScheduleOut.model_validate(service, from_attributes=True) for service in items
    ]

    return PageResponse[BarberScheduleOut](
        items=validated_items,
        total=total,
        page=filter.page,
        size=filter.limit,
        pages=pages,
    )


@router.post(
    "/{barber_id}/schedules",
    description="Create a new barber schedule for the current barber or admin",
    response_model=BarberScheduleOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_barber_schedule(
    barber_id: int,
    body: BarberScheduleCreateIn,
    redis: CacheBackendDep,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.barber))
):
    """
    Create a new barber schedule for the current barber or admin.
    """
    create_data = body.model_dump()

    is_admin = current_user.is_admin()
    is_assigned_barber = (
            current_user.is_barber() and current_user.id == barber_id
        )
    if not (is_admin or is_assigned_barber):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allow to perform this action",
        )

    try:
        barber_schedule = await barber_schedule_service.create_barber_schedule(barber_id, body=create_data, db=db)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    await redis.delete_group("available_slot")
    
    return barber_schedule

@router.patch(
    "/{barber_id}/schedules/{schedule_id}",
    description=" Admins have the authority to edit barbers' schedules." \
    "Barbers can edit their own schedules.",
    response_model=BarberScheduleOut,
    status_code=status.HTTP_200_OK,
)
async def update_barber_schedule(
    barber_id: int,
    schedule_id: int,
    body: BarberScheduleUpdateIn,
    redis: CacheBackendDep,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.barber))
):
    """
    Admins have the authority to edit barbers' schedules.
    Barbers can edit their own schedules.
    """

    new_data = body.model_dump(exclude_unset=True)
    
    is_admin = current_user.is_admin()
    is_assigned_barber = (
        current_user.is_barber() and current_user.id == barber_id
    )
    if not (is_admin or is_assigned_barber):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allow to perform this action",
        )

    try:
        barber_schedule = await barber_schedule_service.update_barber_schedule(
            barber_schedule_id=schedule_id,
            barber_id=barber_id,
            body=new_data,
            db=db
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    await redis.delete_group("available_slot")

    return barber_schedule

@router.delete(
    "/{barber_id}/schedules/{schedule_id}",
    description="Administrators have the authority to delete barbers' work schedules." \
    "Barbers can delete their own work schedules.",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_barber_schedule(
    barber_id: int,
    schedule_id: int,
    redis: CacheBackendDep,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.barber))
):
    """
    Administrators have the authority to delete barbers' work schedules.
    Barbers can delete their own work schedules.
    """

    is_admin = current_user.is_admin()
    is_assigned_barber = (
        current_user.is_barber() and current_user.id == barber_id
    )
    if not (is_admin or is_assigned_barber):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allow to perform this action",
        )

    try:
        await barber_schedule_service.delete_barber_schedule(
            barber_schedule_id=schedule_id,
            barber_id=barber_id,
            db=db
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except SQLAlchemyError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    await redis.delete_group("available_slot")
