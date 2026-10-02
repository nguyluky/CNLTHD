from datetime import datetime, timedelta
import math
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import Booking, BookingService, BookingStatus, Service, User, UserRole, get_db
from app.core.exception import  NotFoundException
from app.dependencies import get_current_active_user, require_roles
from app.schemas.booking import BookingCreateIn, BookingFilterParam, BookingOut, BookingScheduleIn, BookingStatusIn
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    # policy check
    is_admin = current_user.is_admin()
    is_owner_customer = current_user.is_customer() and current_user.id == booking.customer_id
    is_assigned_barber = current_user.is_barber() and current_user.id == booking.barber_id

    if not (is_admin or is_owner_customer or is_assigned_barber):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allow to perform this action"
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
    query = select(Booking)

    # assign query based on user role
    if current_user.is_customer():
        query = query.where(Booking.customer_id == current_user.id)
    elif current_user.is_barber():
        query = query.where(Booking.barber_id == current_user.id)
    elif current_user.is_admin():
        if filter.customer_id:
            query = query.where(Booking.customer_id == filter.customer_id)
        if filter.barber_id:
            query = query.where(Booking.barber_id == filter.barber_id)

    # apply filter to query
    if filter.booking_date:
        query = query.where(Booking.booking_date == filter.booking_date)
    if filter.status:
        query = query.where(Booking.status == filter.status)

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        ) 

    # pagination
    offset = (filter.page - 1) * filter.limit
    paginated_query = query.offset(offset).limit(filter.limit).order_by(Booking.created_at.desc())

    result = await db.scalars(paginated_query)
    items = result.all()

    #convert to Booking
    validated_items = [
        BookingOut.model_validate(booking, from_attributes=True) 
        for booking in items
    ]

    pages = math.ceil(total / filter.limit)
    
    return PageResponse[BookingOut](
        items=validated_items,
        total=total,
        page=filter.page,
        size=filter.limit,
        pages=pages
    )
        
@router.post(
    "",
    description="Allows customers to book schedules",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_booking(
    body: BookingCreateIn,
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
    service_result = await db.scalars(
        select(Service).where(Service.id.in_(body.service_ids))
    )

    services = service_result.all()
    if len(services) != len(body.service_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One of the services does not exist"
        )
    
    total_price = sum(s.price for s in services)
    total_duration = sum(s.duration_minutes for s in services)

    start_dt = datetime.combine(body.booking_date, body.start_time)
    end_dt = start_dt + timedelta(minutes=total_duration)
    end_time = end_dt.time()

    booking = Booking(
        customer_id = current_user.id,
        **body.model_dump(exclude={"service_ids"}),
        end_time = end_time,
        total_price = total_price,
        status = BookingStatus.pending
    )

    db.add(booking)
    await db.flush()

    # create booking_services
    for service in services:
        booking_service = BookingService(
            booking_id = booking.id,
            service_id = service.id,
            price_at_booking = service.price
        )
        db.add(booking_service)

    await db.commit()
    return booking

@router.patch(
    "/{booking_id}/status",
    description="Changes the booking status",
    status_code=status.HTTP_200_OK,
)
async def update_booking_status(
    booking_id: int,
    body: BookingStatusIn,
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    # policy check
    is_admin = current_user.is_admin()
    is_assigned_barber = current_user.is_barber() and current_user.id == booking.barber_id

    if not (is_admin or is_assigned_barber):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allow to perform this action"
        )

    await booking_service.update_booking_status(booking, body.status, db)

    return {"message": "Update Booking status successfully"}

@router.patch(
    "/{booking_id}/cancel",
    description="Updates the booking status to cancelled, unless the booking was completed",
    status_code=status.HTTP_200_OK,
)
async def cancel_booking(
    booking_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        booking = await booking_service.get_booking_by_id(booking_id, db)
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    if booking.status is BookingStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel completed booking"
        )

    # policy check
    is_admin = current_user.is_admin()
    is_owner_customer = current_user.is_customer() and current_user.id == booking.customer_id
    is_assigned_barber = current_user.is_barber() and current_user.id == booking.barber_id

    if not (is_admin or is_owner_customer or is_assigned_barber):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allow to perform this action"
        )

    await booking_service.update_booking_status(booking, BookingStatus.cancelled, db)
    
    return {"message": "Cancel Booking successfully"}

@router.patch(
    "/{booking_id}/reschedule",
    description="Allows owner customers and admins to change the date and time of booking",
    status_code=status.HTTP_200_OK,
)
async def update_booking_schedule(
    booking_id: int,
    body: BookingScheduleIn,
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    # policy check
    is_admin = current_user.is_admin()
    is_owner_customer = current_user.is_customer() and current_user.id == booking.customer_id

    if not (is_admin or is_owner_customer):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allow to perform this action"
        )

    update_data = body.model_dump(exclude_unset=True)

    await booking_service.update_booking_schedule(booking=booking, update_data=update_data, db=db)

    return {"message": "Reschedule Booking successfully"}
