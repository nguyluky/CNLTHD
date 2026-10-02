from app.core.database import BarberSchedule, UserRole, get_db, User
from app.schemas.barber_schedule import BarberScheduleResponse, BarberScheduleCreate, BarberScheduleUpdate
from app.dependencies import get_current_active_user
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/barber_schedules", tags=["Barber Schedule"])

def check_barber_permission(current_user: User, barber_id: int):
    if not current_user.is_admin():
        if not current_user.is_barber() or current_user.id != barber_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this resource"
            )

@router.get(
    "/{barber_id}/schedules",
    description="Get barber schedules for the current barber or admin",
    response_model=list[BarberScheduleResponse],
    status_code=status.HTTP_200_OK,
)
async def get_barber_schedules(
    barber_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
    ):
    """
    Get barber schedules for the current barber or admin.
    """
    check_barber_permission(current_user, barber_id)

    barber_schedules = (await db.scalars(select(BarberSchedule).where(BarberSchedule.barber_id == barber_id))).all()
    if  not barber_schedules or len(barber_schedules) <= 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No barber schedules found")
    
    return barber_schedules

@router.post(
    "/{barber_id}/schedules",
    description="Create a new barber schedule for the current barber or admin",
    response_model=BarberScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_barber_schedule(
    barber_id: int,
    body: BarberScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new barber schedule for the current barber or admin.
    """
    check_barber_permission(current_user, barber_id)

    barber = await db.scalar(
        select(User).where(
            User.id == barber_id,
            User.role == UserRole.barber
        )
    )
    if not barber:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Barber not found")

    barber_schedule = BarberSchedule(
        barber_id=barber_id,
        **body.model_dump()
    )
    db.add(barber_schedule)
    await db.commit()
    await db.refresh(barber_schedule)

    return barber_schedule

@router.patch(
    "/{barber_id}/schedules/{schedule_id}",
    description="Update an existing barber schedule for the current barber or admin",
    response_model=BarberScheduleResponse,
    status_code=status.HTTP_200_OK,
)
async def update_barber_schedule(
    barber_id: int,
    schedule_id: int,
    body: BarberScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update an existing barber schedule for the current barber or admin.
    """
    check_barber_permission(current_user, barber_id)

    barber_schedule = await db.scalar(
        select(BarberSchedule).where(
            BarberSchedule.id == schedule_id,
            BarberSchedule.barber_id == barber_id
        )
    )
    if not barber_schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Barber schedule not found")

    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(barber_schedule, key, value)

    await db.commit()
    await db.refresh(barber_schedule)

    return barber_schedule

@router.delete(
    "/{barber_id}/schedules/{schedule_id}",
    description="Delete an existing barber schedule for the current barber or admin",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_barber_schedule(
    barber_id: int,
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete an existing barber schedule for the current barber or admin.
    """
    check_barber_permission(current_user, barber_id)

    barber_schedule = await db.scalar(
        select(BarberSchedule).where(
            BarberSchedule.id == schedule_id,
            BarberSchedule.barber_id == barber_id
        )
    )
    if not barber_schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Barber schedule not found")

    await db.delete(barber_schedule)
    await db.commit()

    return None
