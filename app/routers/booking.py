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
from app.core.exception import NotFoundException, RequestedServiceForBookingNotFound
from app.dependencies import get_current_active_user, require_roles
from app.schemas.booking import (
    BookingCreateIn,
    BookingFilterParam,
    BookingOut,
    BookingScheduleIn,
    BookingStatusIn,
)
from app.schemas.common import PageResponse
from app.services import booking_service

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.get(
    "/{booking_id}",
    description="Returns booking details, only owner customers or barbers that were assigned can see their dedicated booking detail",
    response_model=BookingOut,
    status_code=status.HTTP_200_OK,
)
async def get_booking_detail(
    booking_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        booking = await booking_service.get_booking_by_id(booking_id, db)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # policy check
    is_admin = current_user.is_admin()
    is_owner_customer = (
        current_user.is_customer() and current_user.id == booking.customer_id
    )
    is_assigned_barber = (
        current_user.is_barber() and current_user.id == booking.barber_id
    )

    if not (is_admin or is_owner_customer or is_assigned_barber):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allow to perform this action",
        )

    return booking


@router.get(
    "",
    description="Returns a list of booking, the result varies based on the user's role",
    response_model=PageResponse[BookingOut],
    status_code=status.HTTP_200_OK,
)
async def get_bookings(
    filter: Annotated[BookingFilterParam, Query()],
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        items, total, pages = await booking_service.get_filtered_bookings_for_user(
            filter=filter, current_user=current_user, db=db
        )
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # convert to Booking
    validated_items = [
        BookingOut.model_validate(booking, from_attributes=True) for booking in items
    ]

    return PageResponse[BookingOut](
        items=validated_items,
        total=total,
        page=filter.page,
        size=filter.limit,
        pages=pages,
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
    current_user: User = Depends(require_roles(UserRole.customer)),
    db: AsyncSession = Depends(get_db),
):
    """
    Creates booking.
    - **barber_id**: Choosen barber's id
    - **booking_date**: Choosen booking date
    - **start_time**: Choosen time of the day the booking is scheduled
    - **service_ids**: List of choosen service ids
    """

    try:
        booking = await booking_service.create_booking(
            current_user=current_user, 
            barber_id=body.barber_id, 
            booking_date=body.booking_date, 
            start_time=body.start_time, 
            service_ids=body.service_ids, 
            db=db,
        )
    except RequestedServiceForBookingNotFound as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

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
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.barber)),
    db: AsyncSession = Depends(get_db),
):
    """
    Update booking status.
    - **status**: new status for booking
    """

    try:
        booking = await booking_service.get_booking_by_id(booking_id, db)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # policy check
    is_admin = current_user.is_admin()
    is_assigned_barber = (
        current_user.is_barber() and current_user.id == booking.barber_id
    )

    if not (is_admin or is_assigned_barber):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allow to perform this action",
        )

    await booking_service.update_booking_status(booking, body.status, db)
    await redis.delete_group("available_slot")

    return {"message": "Update Booking status successfully"}


@router.patch(
    "/{booking_id}/cancel",
    description="Updates the booking status to cancelled, unless the booking was completed",
    status_code=status.HTTP_200_OK,
)
async def cancel_booking(
    booking_id: int,
    redis: CacheBackendDep,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        booking = await booking_service.get_booking_by_id(booking_id, db)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    if booking.status is BookingStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel completed booking",
        )

    # policy check
    is_admin = current_user.is_admin()
    is_owner_customer = (
        current_user.is_customer() and current_user.id == booking.customer_id
    )
    is_assigned_barber = (
        current_user.is_barber() and current_user.id == booking.barber_id
    )

    if not (is_admin or is_owner_customer or is_assigned_barber):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allow to perform this action",
        )

    await booking_service.update_booking_status(booking, BookingStatus.cancelled, db)
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
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.customer)),
    db: AsyncSession = Depends(get_db),
):
    """
    Reschedule booking.
    - **booking_date**: Optional new booking date
    - **start_time**: Optional new time of the day the booking is scheduled
    """

    try:
        booking = await booking_service.get_booking_by_id(booking_id, db)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # policy check
    is_admin = current_user.is_admin()
    is_owner_customer = (
        current_user.is_customer() and current_user.id == booking.customer_id
    )

    if not (is_admin or is_owner_customer):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allow to perform this action",
        )

    update_data = body.model_dump(exclude_unset=True)

    await booking_service.update_booking_schedule(
        booking=booking, update_data=update_data, db=db
    )
    await redis.delete_group("available_slot")

    return {"message": "Reschedule Booking successfully"}
