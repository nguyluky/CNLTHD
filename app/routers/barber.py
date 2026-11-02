from datetime import date
import json
from urllib import response
from redis_fastapi import CacheBackendDep
from app.schemas import barber
from app.schemas.barber import BarberFilterParam, BarberOut
from app.schemas.barber_schedule import AvailableSlotOut
from app.schemas.common import PageResponse, create_page_response
from typing import Annotated
from fastapi import APIRouter, HTTPException, Query, Response, status
from app.services.barber_service import *

router = APIRouter(prefix="/barbers", tags=["Barber"])


@router.get(
    "",
    summary="Get all barbers.",
    response_model=PageResponse[BarberOut],
    status_code=status.HTTP_200_OK,
)
async def get_barbers(
    filter: Annotated[BarberFilterParam, Query()],
    barber_service: BarberServiceDep,
):
    items, total = await barber_service.get_filtered_barbers(filter=filter)

    return create_page_response(
        items=items,
        total=total,
        page=filter.page,
        size=filter.limit,
    )


@router.get(
    "/{barber_id}",
    summary="Get barber by ID.",
    response_model=BarberOut,
    status_code=status.HTTP_200_OK,
)
async def get_barber(
    barber_id: int,
    barber_service: BarberServiceDep,
):

    barber = await barber_service.get_barber_by_id(barber_id)

    response = BarberOut.model_validate(barber)

    return response


@router.get(
    "/{barber_id}/available-slots",
    summary="Returns the specified barber free time slots in the specified date.",
    response_model=AvailableSlotOut,
    status_code=200,
)
async def get_available_slots(
    barber_id: int,
    barber_service: BarberServiceDep,
    redis: CacheBackendDep,
    response: Response,
    booking_date: date = Query(..., description="Specified date"),
    slot_duration: int = Query(30, description="specified slot duration in minutes"),
):
    """
    Returns the specified barber free time slots in the specified date, the client can further specify the duration of each time slot, with the default duration being 30 minutes.
    If the barber has assigned bookings on the specified date, the slots which overlap with the booking time frames will not show up.
    """

    available_slots = []

    redis_key = (
        f"barber:{barber_id}:available_slots:{booking_date.isoformat()}:{slot_duration}"
    )
    cached_data = await redis.get(redis_key, eviction_group="available_slot")
    if cached_data:
        available_slots = json.loads(cached_data)
        response.headers["X-Cache"] = "HIT"
    else:
        available_slots = await barber_service.get_available_slot_minutes(
            barber_id=barber_id, target_date=booking_date, slot_duration=slot_duration
        )

        # cache into redis
        await redis.set(
            redis_key, json.dumps(available_slots), ttl=300, eviction_group="available_slot"
        )

        response.headers["X-Cache"] = "MISS"

    return {
        "booking_date": booking_date,
        "slot_duration_minutes": slot_duration,
        "available_slots": available_slots,
    }


map_exception = {
    BarberNotFoundException: lambda e: HTTPException(
        status_code=404, detail=e or "Barber not found"
    ),
}
