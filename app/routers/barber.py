from datetime import date
import json
from urllib import response
from redis_fastapi import CacheBackendDep
from app.schemas.barber import BarberFilterParam, BarberOut
from app.schemas.barber_schedule import AvailableSlotOut
from app.schemas.common import PageResponse
from typing import Annotated
from fastapi import APIRouter, HTTPException, Query, status
from app.services.barber_service import *
from redis_fastapi import cache, cache_evict, cache_put, default_key_builder

router = APIRouter(prefix="/barbers", tags=["Barber"])

@router.get(
    "",
    description="Get all barbers",
    response_model=PageResponse[BarberOut],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(cache(ttl=300, eviction_group="barber"))]
)
async def get_barbers(
    filter: Annotated[BarberFilterParam, Query()],
    barber_service: BarberServiceDep,
    ):
    """
    Get all barbers.
    """

    items, total, pages = await barber_service.get_filtered_barbers(filter=filter)

    validated_items = [
        BarberOut.model_validate(service) for service in items
    ]

    response = PageResponse[BarberOut](
        items=validated_items,
        total=total,
        page=filter.page,
        size=filter.limit,
        pages=pages,
    )

    return response


@router.get(
    "/{barber_id}",
    description="Get barber by ID",
    response_model=BarberOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(cache(ttl=300, eviction_group="barber"))]
)
async def get_barber(
    barber_id: int,
    barber_service: BarberServiceDep,
):
    """
    Get a barber by ID.
    """

    barber = await barber_service.get_barber_by_id(barber_id)

    response = BarberOut.model_validate(barber)

    return response

@router.get(
    "/{barber_id}/available-slots",
    description="Returns the specified barber free time slots in the specified date, the client can further specify the duration of each time slot",
    response_model=AvailableSlotOut,
    status_code=200,
)
async def get_available_slots(
    barber_id: int,
    barber_service: BarberServiceDep,
    redis: CacheBackendDep,
    booking_date: date = Query(..., description="Specified date"),
    slot_duration: int = Query(30, description="specified slot duration in minutes"),
):
    available_slots = []
    
    redis_key = f"barber:{barber_id}:available_slots:{booking_date.isoformat()}:{slot_duration}"
    cached_data = await redis.get(redis_key, eviction_group="available_slot")
    if cached_data:
        available_slots = json.loads(cached_data)
    
    available_slots = await barber_service.get_available_slot_minutes(
        barber_id=barber_id, 
        target_date=booking_date,
        slot_duration=slot_duration
    )

    # cache into redis
    await redis.set(redis_key, json.dumps(available_slots), ttl=300, eviction_group="available_slot")
    
    return {
        "booking_date": booking_date,
        "slot_duration_minutes": slot_duration,
        "available_slots": available_slots
    }

map_exception = {
    BarberNotFoundException: lambda e: HTTPException(
        status_code=404, detail=e or "Barber not found"
    ),
}