from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis_fastapi import CacheBackendDep
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import (
    BookingStatus,
    User,
    UserRole,
    get_db,
)
from app.core.exception import NotFoundException
from app.dependencies import get_current_active_user, require_roles
from app.schemas.booking import (
    BookingCreateIn,
    BookingFilterParam,
    BookingOut,
    BookingScheduleIn,
    BookingStatusIn,
)
from app.schemas.common import create_page_response
from app.schemas.common import PageResponse
from app.services import booking_service
from app.services.booking_service import BookingServiceDep, BookingServicePolicyDep, BookingAlreadyFinalizedException, RequestedServiceForBookingNotFound

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.get(
    "/{booking_id}",
    description="Returns booking details, only owner customers or barbers that were assigned can see their dedicated booking detail",
    response_model=BookingOut,
    status_code=status.HTTP_200_OK,
)
async def get_booking_detail(
    booking_id: int,
    booking_service: BookingServiceDep,
    booking_service_policy: BookingServicePolicyDep,
    # current_user: User = Depends(get_current_active_user),
):
    booking = await booking_service.get_booking_by_id(booking_id)

    # policy check
    booking_service_policy.has_permission_to_view_booking(booking)

    return booking


@router.get(
    "",
    description="Returns a list of booking, the result varies based on the user's role",
    response_model=PageResponse[BookingOut],
    status_code=status.HTTP_200_OK,
)
async def get_bookings(
    filter_: Annotated[BookingFilterParam, Query()],
    booking_service: BookingServiceDep,
    booking_service_policy: BookingServicePolicyDep,
):
    filter_ = booking_service_policy.apply_user_filter(filter_)

    items, total = await booking_service.get_filtered_bookings(
        page=filter_.page,
        limit=filter_.limit,
        booking_date=filter_.booking_date,
        status=filter_.status,
        barber_id=filter_.barber_id,
        customer_id=filter_.customer_id,
    )

    return create_page_response(
        items=items,
        total=total,
        page=filter_.page,
        size=filter_.limit,
    )


@router.post(
    "",
    description="Allows customers to book schedules",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_booking(
    body: BookingCreateIn,
    redis: CacheBackendDep,
    booking_service: BookingServiceDep,
    current_user: User = Depends(require_roles(UserRole.customer)),
):
    """
    Creates booking.
    - **barber_id**: Choosen barber's id
    - **booking_date**: Choosen booking date
    - **start_time**: Choosen time of the day the booking is scheduled
    - **service_ids**: List of choosen service ids
    """

    booking = await booking_service.create_booking(
        user_id=current_user.id,
        barber_id=body.barber_id,
        booking_date=body.booking_date,
        start_time=body.start_time,
        service_ids=body.service_ids,
    )

    await redis.delete_group("available_slot")

    return booking


@router.patch(
    "/{booking_id}/status",
    description="Changes the booking status",
    status_code=status.HTTP_200_OK,
)
async def update_booking_status(
    booking_id: int,
    body: BookingStatusIn,
    redis: CacheBackendDep,
    booking_service: BookingServiceDep,
    booking_service_policy: BookingServicePolicyDep,
):
    """
    Update booking status.
    - **status**: new status for booking
    """

    booking = await booking_service.get_booking_by_id(booking_id)


    booking_service_policy.has_permission_to_view_booking(booking)

    await booking_service.update_booking_status(booking=booking, new_status=body.status)

    await redis.delete_group("available_slot")

    return booking


@router.patch(
    "/{booking_id}/cancel",
    description="Updates the booking status to cancelled, unless the booking was completed",
    status_code=status.HTTP_200_OK,
)
async def cancel_booking(
    booking_id: int,
    redis: CacheBackendDep,
    booking_service: BookingServiceDep,
    booking_service_policy: BookingServicePolicyDep,
    db: AsyncSession = Depends(get_db),
):
    booking = await booking_service.get_booking_by_id(booking_id)

    # policy check
    booking_service_policy.has_permission_to_view_booking(booking)

    await booking_service.update_booking_status(booking=booking, new_status=BookingStatus.cancelled)

    await redis.delete_group("available_slot")

    return {"message": "Cancel Booking successfully"}


@router.patch(
    "/{booking_id}/reschedule",
    description="Allows owner customers and admins to change the date and time of booking",
    status_code=status.HTTP_200_OK,
)
async def update_booking_schedule(
    booking_id: int,
    body: BookingScheduleIn,
    redis: CacheBackendDep,
    booking_service: BookingServiceDep,
    booking_service_policy: BookingServicePolicyDep,
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.customer)),
):
    """
    Reschedule booking.
    - **booking_date**: Optional new booking date
    - **start_time**: Optional new time of the day the booking is scheduled
    """

    booking = await booking_service.get_booking_by_id(booking_id)

    # policy check
    booking_service_policy.has_permission_to_view_booking(booking)


    await booking_service.update_booking_schedule(
        booking=booking, booking_date=body.booking_date, start_time=body.start_time
    )
    await redis.delete_group("available_slot")

    return {"message": "Reschedule Booking successfully"}

map_exception  = {
    RequestedServiceForBookingNotFound: lambda e: HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail=e or "Requested service for booking not found"
    ),
    BookingAlreadyFinalizedException: lambda e: HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail=e or "Cannot update status of a completed or cancelled booking"
    ),
}