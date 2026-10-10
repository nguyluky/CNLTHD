from datetime import date, datetime, time, timedelta
import math
from typing import Annotated
from decimal import Decimal

from fastapi import Depends
from redis_fastapi import CacheBackend
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import (
    Booking,
    # BookingService,
    BookingStatus,
    Service,
    User,
    get_db,
)
from app.core.database import BookingService as BookingServiceModel

# from app.core.exception import RequestedServiceForBookingNotFound
from app.dependencies import get_current_active_user
from app.schemas.booking import BookingFilterParam

from app.services.share import NotFoundException, NotAllowedException, ServiceException


class _BookingServiceException(ServiceException):
    pass

class BookingAlreadyFinalizedException(_BookingServiceException):
    """Lỗi khi cập nhật lịch hẹn đã hoàn thành"""

    pass


class RequestedServiceForBookingNotFound(_BookingServiceException):
    """Lỗi khi dịch vụ được yêu cầu để đặt lịch hẹn không tồn tại"""

    pass

class UserNotAllowedToViewBookingException(_BookingServiceException):
    """Lỗi khi người dùng không được phép xem lịch hẹn"""

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
            raise NotFoundException("Booking detail not found")

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

        if total == 0:
            raise NotFoundException("Booking not found")

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
            raise RequestedServiceForBookingNotFound(
                "One of the services does not exist"
            )

        total_price = sum((s.price for s in services), Decimal(0))
        total_duration = sum(s.duration_minutes for s in services)

        start_dt = datetime.combine(booking_date, start_time)
        end_dt = start_dt + timedelta(minutes=total_duration)
        end_time = end_dt.time()

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

        return booking

    async def update_booking_status(
        self, *, booking: Booking, new_status: BookingStatus
    ) -> Booking:
        if booking.status in [BookingStatus.completed, BookingStatus.cancelled]:
            raise BookingAlreadyFinalizedException(
                "Cannot update status of a completed or cancelled booking"
            )

        booking.status = new_status
        await self.db.commit()
        await self.db.refresh(booking)

        return booking
    
    async def update_booking_schedule(
        self, *, booking: Booking, booking_date: date | None = None,
    start_time: time | None = None):
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
            booking.booking_date = booking_date

        if start_time:
            start_dt = datetime.combine(booking.booking_date, start_time)
            end_dt = start_dt + timedelta(minutes=total_duration)
            end_time = end_dt.time()

            booking.start_time = start_time
            booking.end_time = end_time

        await self.db.commit()
        await self.db.refresh(booking)

        return booking
        

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
