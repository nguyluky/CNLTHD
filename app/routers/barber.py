from datetime import date

from redis_fastapi import CacheBackendDep

from app.core.database import get_db
from app.schemas.barber import BarberFilterParam, BarberOut
from app.schemas.barber_schedule import AvailableSlotOut
from app.schemas.common import PageResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.exception import NotFoundException
from app.services import barber_service
router = APIRouter(prefix="/barbers", tags=["Barber"])

@router.get(
    "",
    description="Get all barbers",
    response_model=PageResponse[BarberOut],
    status_code=status.HTTP_200_OK,
)
async def get_barbers(
    filter: Annotated[BarberFilterParam, Query()],
    db: AsyncSession = Depends(get_db)
    ):
    """
    Get all barbers.
    """
    try:
        items, total, pages = await barber_service.get_filtered_barbers(filter=filter, db=db)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    validated_items = [
        BarberOut.model_validate(service, from_attributes=True) for service in items
    ]

    return PageResponse[BarberOut](
        items=validated_items,
        total=total,
        page=filter.page,
        size=filter.limit,
        pages=pages,
    )


@router.get(
    "/{barber_id}",
    description="Get barber by ID",
    response_model=BarberOut,
    status_code=status.HTTP_200_OK,
)
async def get_barber(
    barber_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a barber by ID.
    """
    try:
        barber = await barber_service.get_barber_by_id(barber_id, db=db)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return barber

@router.get(
    "/{barber_id}/available-slots",
    response_model=AvailableSlotOut,
    status_code=200,
)
async def get_available_slots(
    barber_id: int,
    redis: CacheBackendDep,
    booking_date: date = Query(..., description="Ngày tra cứu (YYYY-MM-DD)"),
    slot_duration: int = Query(30, description="Độ dài khung giờ (phút)"),
    db: AsyncSession = Depends(get_db),
):
    available_slots = await barber_service.get_available_slot_minutes(
        barber_id=barber_id, 
        target_date=booking_date,
        db=db,
        redis=redis,
        slot_duration=slot_duration
    )
    return {
        "booking_date": booking_date,
        "slot_duration_minutes": slot_duration,
        "available_slots": available_slots
    }