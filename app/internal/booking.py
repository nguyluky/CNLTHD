from datetime import datetime, timedelta
from typing import Annotated
from xml.etree.ElementInclude import DEFAULT_MAX_INCLUSION_DEPTH

from fastapi import APIRouter, Depends, HTTPException, Query, status

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import Booking, BookingService, BookingStatus, Service, User, UserRole, get_db
from app.dependencies import get_current_active_user, require_roles
from app.schemas.booking import BookingCreateIn, BookingFilterParam, BookingOut, BookingStatusIn
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
    booking = await booking_service.get_booking_detail(booking_id, db)

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking detail not found"
        )

    is_admin = current_user.is_admin()
    is_owner_customer = current_user.is_customer() and current_user.id == booking.customer_id
    is_assigned_barber = current_user.is_barber() and current_user.id == booking.barber_id

    if not (is_admin or is_owner_customer or is_assigned_barber):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are unauthorized to perform this action"
        )

    return booking

@router.get(
    "",
    description="Returns a list of booking, the result varies based on the user's role",
    response_model=BookingOut,
    status_code=status.HTTP_200_OK,
)
async def get_bookings(
    filter: Annotated[BookingFilterParam, Query()],
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Booking)
    if current_user.is_customer():
        query = query.where(Booking.customer_id == current_user.id)
    elif current_user.is_barber():
        query = query.where(Booking.barber_id == current_user.id)
    elif current_user.is_admin():
        if filter.customer_id:
            query = query.where(Booking.customer_id == filter.customer_id)
        if filter.barber_id:
            query = query.where(Booking.barber_id == filter.barber_id)

    if filter.booking_date:
        query = query.where(Booking.booking_date == filter.booking_date)
    if filter.status:
        query = query.where(Booking.status == filter.status)

    # pagination
    offset = (filter.page - 1) * filter.limit
    query = query.offset(offset).limit(filter.limit).order_by(Booking.created_at.desc())

    result = await db.scalars(query)
    booking_result = result.all()

    if not booking_result or len(booking_result) <= 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        ) 
    
    return booking_result
        
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
    if not current_user.is_customer():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are unauthorized to perform this action"
        )
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
    response_model=BookingOut,
    status_code=status.HTTP_200_OK,
)
async def update_booking_status(
    booking_id: int,
    body: BookingStatusIn,
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.barber)),
    db: AsyncSession = Depends(get_db),
):
    booking = await booking_service.get_booking_detail(booking_id, db)
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking detail not found"
        )

    is_admin = current_user.is_admin()
    is_assigned_barber = current_user.is_barber() and current_user.id == booking.barber_id

    if not (is_admin or is_assigned_barber):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are unauthorized to perform this action"
        )

    booking.status = body.status
    await db.commit()
    await db.refresh(booking)

    return booking

@router.patch(
    "/{booking_id}/cancel",
    description="Updates the booking status to cancelled",
    response_model=BookingOut,
    status_code=status.HTTP_200_OK,
)
async def cancle_booking(
    booking_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    booking = await booking_service.get_booking_detail(booking_id, db)
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking detail not found"
        )

    is_admin = current_user.is_admin()
    is_owner_customer = current_user.is_customer() and current_user.id == booking.customer_id
    is_assigned_barber = current_user.is_barber() and current_user.id == booking.barber_id

    if not (is_admin or is_owner_customer or is_assigned_barber):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are unauthorized to perform this action"
        )

    booking.status = BookingStatus.cancelled
    await db.commit()
    await db.refresh(booking)

    return booking
