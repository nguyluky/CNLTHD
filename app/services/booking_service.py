from datetime import date, datetime, time, timedelta
import math
from typing import Annotated
from decimal import Decimal

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import (
    Booking,
    BookingStatus,
    Service,
    User,
    get_db,
)
from app.core.database import BookingService as BookingServiceModel
from app.dependencies import get_current_active_user
from app.routers import barber
from app.routers import service_logger
from app.schemas.booking import BookingFilterParam
from app.core.exception import DomainException
from app.seeder import BarberSchedule


class _BookingServiceException(DomainException):
    pass

class BookingAlreadyFinalizedException(_BookingServiceException):
    """Raise this exception during a status update if booking status is completed."""

    pass


class RequestedServiceForBookingNotFoundException(_BookingServiceException):
    """Raise this exception if the requested service from a create booking request does not exists."""

    pass

class UserNotAllowedToViewBookingException(_BookingServiceException):
    """Raise this exception if the user is not allowed to view booking."""

    pass

class BookingNotFoundException(_BookingServiceException):
    """Raise this exception if the booking in question does not exists."""

    pass

class RequestedBarberDoesNotWorkInRequestedBookingDateException(_BookingServiceException):
    """Raise this exception if the requested barber does not have a schedule on the requested booking date."""

    pass

class RequestedBookingTimeIsNotWithinScheduleException(_BookingServiceException):
    """Raise this exception if the requested booking time is not within the requested barber's schedule"""

    pass

class RequestedBookingTimeOverlappedWithExistedBookingException(_BookingServiceException):
    """Raise this exception if the requested booking time overlapped with the requested barber assigned bookings"""
    
    pass


class BookingServicePolicy:
    def __init__(self, user: User):
        self.user = user

    def has_permission_to_view_booking(self, booking: Booking):
        is_admin = self.user.is_admin()
        is_owner_customer = (
            self.user.is_customer() and self.user.id == booking.customer_id
        )
        is_assigned_barber = self.user.is_barber() and self.user.id == booking.barber_id

        if not is_admin and (not is_owner_customer and not is_assigned_barber):
            service_logger.warning(
                "Unauthorized request to booking from user",
                extra={"user_id":self.user.id, "role": self.user.role}
            )
            raise UserNotAllowedToViewBookingException("You do not have permission to view this booking.")

    def apply_user_filter(
        self,
        filter: BookingFilterParam,
    ):
        """
        admin thì có thể filter theo customer_id hoặc barber_id,
        còn customer thì chỉ được filter theo chính mình, barber cũng vậy

        """

        new_filter = filter.model_copy()

        if self.user.is_customer():
            new_filter.customer_id = self.user.id
        elif self.user.is_barber():
            new_filter.barber_id = self.user.id

        return new_filter


class BookingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_booking_by_id(self, booking_id: int) -> Booking:
        booking = (
            await self.db.scalars(
                select(Booking)
                .where(Booking.id == booking_id)
                .options(selectinload(Booking.services))
            )
        ).first()

        if not booking:
            service_logger.warning(
                "Booking look up failed: record not found", 
                extra={"booking_id": booking_id}
            )
            raise BookingNotFoundException("Booking detail not found")

        return booking

    async def get_filtered_bookings(
        self,
        *,
        page: int,
        limit: int,
        booking_date: date | None = None,
        status: BookingStatus | None = None,
        barber_id: int | None = None,
        customer_id: int | None = None,
    ):
        query = select(Booking)

        if booking_date:
            query = query.where(Booking.booking_date == booking_date)
        if status:
            query = query.where(Booking.status == status)
        if barber_id:
            query = query.where(Booking.barber_id == barber_id)
        if customer_id:
            query = query.where(Booking.customer_id == customer_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # if total == 0:
        #     raise BookingNotFoundException("Booking not found")

        offset = (page - 1) * limit
        paginated_query = (
            query.offset(offset).limit(limit).order_by(Booking.created_at.desc())
        )

        result = await self.db.scalars(paginated_query)
        items = result.all()

        return items, total

    async def create_booking(
        self,
        *,
        user_id: int,
        barber_id: int,
        booking_date: date,
        start_time: time,
        service_ids: list[int],
    ) -> Booking:
        service_result = await self.db.scalars(
            select(Service).where(Service.id.in_(service_ids))
        )

        services = service_result.all()
        if len(services) != len(service_ids):
            service_logger.warning(
                "Service for booking look up failed: One of the services does not exist"
            )
            raise RequestedServiceForBookingNotFoundException(
                "One of the services does not exist"
            )

        total_price = sum((s.price for s in services), Decimal(0))
        total_duration = sum(s.duration_minutes for s in services)

        start_dt = datetime.combine(booking_date, start_time)
        end_dt = start_dt + timedelta(minutes=total_duration)
        end_time = end_dt.time()

        try:
            await self.check_for_valid_booking_date(
                barber_id=barber_id, 
                booking_date=booking_date,
            )

            await self.check_for_within_schedule(
                barber_id=barber_id, 
                booking_date=booking_date, 
                start_time=start_time, 
                end_time=end_time
            )

            await self.check_for_booking_overlapping(
                barber_id=barber_id, 
                booking_date=booking_date, 
                start_time=start_time, 
                end_time=end_time
            )
        except RequestedBarberDoesNotWorkInRequestedBookingDateException as e:
            raise e
        except RequestedBookingTimeIsNotWithinScheduleException as e:
            raise e
        except RequestedBookingTimeOverlappedWithExistedBookingException as e:
            raise e


        booking = Booking()
        booking.customer_id = user_id
        booking.barber_id = barber_id
        booking.booking_date = booking_date
        booking.start_time = start_time
        booking.end_time = end_time
        booking.total_price = total_price
        booking.status = BookingStatus.pending

        self.db.add(booking)
        await self.db.flush()

        for service in services:
            booking_service = BookingServiceModel(
                booking_id=booking.id,
                service_id=service.id,
                price_at_booking=service.price,
            )
            self.db.add(booking_service)

        await self.db.commit()

        service_logger.info(
            "Booking created successfully",
            extra={"booking_id": booking.id}
        )

        return booking

    async def update_booking_status(
        self, *, booking: Booking, new_status: BookingStatus
    ) -> Booking:
        if booking.status in [BookingStatus.completed, BookingStatus.cancelled]:
            service_logger.warning(
                "Booking update fail: Cannot update status of a completed or cancelled booking",
                extra={"booking_id": booking.id, "status": booking.status}
            )
            raise BookingAlreadyFinalizedException(
                "Cannot update status of a completed or cancelled booking"
            )

        booking.status = new_status
        await self.db.commit()
        await self.db.refresh(booking)

        service_logger.info(
            "Booking status updated successfully",
            extra={"booking_id": booking.id, "new_status": booking.status}
        )

        return booking
    
    async def update_booking_schedule(
        self, *, booking: Booking, booking_date: date | None = None,
        start_time: time | None = None
    ):
        booking_services = (
            await self.db.scalars(
                select(BookingServiceModel).where(
                    BookingServiceModel.booking_id == booking.id
                )
            )
        ).all()

        total_duration = 0
        for bs in booking_services:
            service = (
                await self.db.scalars(select(Service).where(Service.id == bs.service_id))
            ).first()
            if service:
                total_duration += service.duration_minutes

        if booking_date:
            try:
                await self.check_for_valid_booking_date(
                    booking_date=booking_date,
                    barber_id=booking.barber_id
                )
            except RequestedBarberDoesNotWorkInRequestedBookingDateException as e:
                raise e
            
            booking.booking_date = booking_date

        if start_time:
            start_dt = datetime.combine(booking.booking_date, start_time)
            end_dt = start_dt + timedelta(minutes=total_duration)
            end_time = end_dt.time()

            try: 
                await self.check_for_within_schedule(
                    barber_id=booking.barber_id, 
                    booking_date=booking.booking_date, 
                    start_time=start_time, 
                    end_time=end_time
                )

                await self.check_for_booking_overlapping(
                    barber_id=booking.barber_id, 
                    booking_date=booking.booking_date, 
                    start_time=start_time, 
                    end_time=end_time
                )
            except RequestedBookingTimeIsNotWithinScheduleException as e:
                raise e
            except RequestedBookingTimeOverlappedWithExistedBookingException as e:
                raise e 

            booking.start_time = start_time
            booking.end_time = end_time

        await self.db.commit()
        await self.db.refresh(booking)

        service_logger.info(
            "Booking schedule updated successfully",
            extra={"booking_id": booking.id}
        )

        return booking

    async def check_for_valid_booking_date(self, booking_date: date, barber_id: int):
        barber_schedule = await self.db.scalar(
            select(BarberSchedule)
            .where(
                BarberSchedule.barber_id == barber_id,
                BarberSchedule.date_of_week == booking_date.weekday()
            )
        )

        if not barber_schedule:
            raise RequestedBarberDoesNotWorkInRequestedBookingDateException(
                "The requested barber does not work on the requested booking date"
            )

        return barber_schedule

    async def check_for_within_schedule(self, booking_date: date, barber_id: int, start_time: time, end_time: time):
        barber_schedule = await self.db.scalar(
            select(BarberSchedule)
            .where(
                BarberSchedule.barber_id == barber_id,
                BarberSchedule.date_of_week == booking_date.weekday()
            )
        )

        if barber_schedule is not None:
            schedule_start = barber_schedule.start_time
            schedule_end = barber_schedule.end_time
            is_within_schedule = schedule_start < start_time and end_time < schedule_end
            if not is_within_schedule:
                raise RequestedBookingTimeIsNotWithinScheduleException(
                    "The requested booking time is not within schedule"
                )

    async def check_for_booking_overlapping(self, booking_date: date, barber_id: int, start_time: time, end_time: time):
        existed_bookings = (await self.db.scalars(
            select(Booking)
            .where(
                Booking.barber_id == barber_id,
                Booking.booking_date == booking_date
            )
        )).all()

        if existed_bookings is not None or len(existed_bookings) > 0:
            is_overlapping = any(
                max(start_time, b.start_time) < min(end_time, b.end_time)
                for b in existed_bookings
            )

            if is_overlapping:
                raise RequestedBookingTimeOverlappedWithExistedBookingException(
                    "The requested booking time is overlapping with existed bookings"
                )
        

async def get_booking_service(db: AsyncSession = Depends(get_db)):
    return BookingService(db)


BookingServiceDep = Annotated[BookingService, Depends(get_booking_service)]


async def get_booking_service_policy(
    current_user: User = Depends(get_current_active_user),
):
    return BookingServicePolicy(current_user)


BookingServicePolicyDep = Annotated[
    BookingServicePolicy, Depends(get_booking_service_policy)
]
