import asyncio
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from app.core.logger import service_logger
from app.core.database import (
    BarberSchedule,
    Base,
    Booking,
    BookingService,
    BookingStatus,
    Service,
    User,
    UserRole,
    SessionLocal,
    engine,
)
from app.core.config import configEnv
from app.main import configure_logging, shutdown_logging


# =========================================================
# SEED CONFIGURATION
# =========================================================

BARBER_COUNT = 20
CUSTOMER_COUNT = 50
HISTORICAL_BOOKING_DAYS = 14

ADMIN_PASSWORD = "Admin@123"
BARBER_PASSWORD = "Barber@123"
CUSTOMER_PASSWORD = "Customer@123"


# =========================================================
# SERVICES
# =========================================================

SERVICE_DATA = [
    {
        "name": "Cắt tóc nam tiêu chuẩn",
        "description": "Cắt tóc, cạo mặt, vuốt sáp",
        "price": Decimal("70000.00"),
        "duration_minutes": 30,
        "is_active": True,
    },
    {
        "name": "Gội đầu thư giãn",
        "description": "Gội đầu massage 20 phút",
        "price": Decimal("40000.00"),
        "duration_minutes": 20,
        "is_active": True,
    },
    {
        "name": "Uốn tóc",
        "description": "Uốn phồng, uốn xoăn",
        "price": Decimal("250000.00"),
        "duration_minutes": 90,
        "is_active": True,
    },
    {
        "name": "Nhuộm tóc",
        "description": "Nhuộm màu thời trang",
        "price": Decimal("350000.00"),
        "duration_minutes": 120,
        "is_active": True,
    },
    {
        "name": "Hấp phục hồi tóc",
        "description": "Chăm sóc và phục hồi tóc hư tổn",
        "price": Decimal("150000.00"),
        "duration_minutes": 45,
        "is_active": True,
    },
    {
        "name": "Cạo râu",
        "description": "Cạo râu và chăm sóc da mặt",
        "price": Decimal("50000.00"),
        "duration_minutes": 20,
        "is_active": True,
    },
    {
        "name": "Cắt tóc trẻ em",
        "description": "Dịch vụ cắt tóc dành cho trẻ em",
        "price": Decimal("60000.00"),
        "duration_minutes": 30,
        "is_active": True,
    },
    {
        "name": "Dịch vụ ngừng kinh doanh",
        "description": "Dịch vụ dùng để kiểm tra lọc dịch vụ inactive",
        "price": Decimal("100000.00"),
        "duration_minutes": 30,
        "is_active": False,
    },
]


# =========================================================
# DATABASE RESET
# =========================================================

async def reset_database():
    service_logger.warning("Clearing Database...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    service_logger.info("Database cleared")


# =========================================================
# USER FACTORY
# =========================================================

async def create_user(
    full_name: str,
    email: str,
    phone: str,
    role: UserRole,
    password: str,
):
    user = User(
        full_name=full_name,
        email=email,
        phone=phone,
        role=role,
    )

    await user.async_hash_password(password)

    return user


# =========================================================
# SEED DATA
# =========================================================

async def seed_data():
    service_logger.info(
        f"Seeding Database: {configEnv.DATABASE_URL}"
    )

    await reset_database()

    async with SessionLocal() as db:
        service_logger.info("Seeding services...")

        # -------------------------------------------------
        # 1. SERVICES
        # -------------------------------------------------

        services = [
            Service(**data)
            for data in SERVICE_DATA
        ]

        db.add_all(services)
        await db.flush()

        active_services = [
            service
            for service in services
            if service.is_active
        ]

        # -------------------------------------------------
        # 2. ADMIN
        # -------------------------------------------------

        service_logger.info("Seeding admin...")

        admin = await create_user(
            full_name="System Admin",
            email="admin@salon.com",
            phone="0900000000",
            role=UserRole.admin,
            password=ADMIN_PASSWORD,
        )

        db.add(admin)

        # -------------------------------------------------
        # 3. BARBERS
        # -------------------------------------------------

        service_logger.info(
            f"Seeding {BARBER_COUNT} barbers..."
        )

        barbers = []

        for index in range(1, BARBER_COUNT + 1):
            barber = await create_user(
                full_name=f"Barber {index:03d}",
                email=f"barber{index:03d}@salon.test",
                phone=f"091{index:07d}",
                role=UserRole.barber,
                password=BARBER_PASSWORD,
            )

            barbers.append(barber)

        db.add_all(barbers)

        # -------------------------------------------------
        # 4. CUSTOMERS
        # -------------------------------------------------

        service_logger.info(
            f"Seeding {CUSTOMER_COUNT} customers..."
        )

        customers = []

        for index in range(1, CUSTOMER_COUNT + 1):
            full_name = f"Customer {index:03d}"
            email = f"customer{index:03d}@salon.test"
            phone = f"093{index:07d}"

            customer = await create_user(
                full_name=full_name,
                email=email,
                phone=phone,
                role=UserRole.customer,
                password=CUSTOMER_PASSWORD,
            )

            customers.append(customer)

        db.add_all(customers)

        # Ensure user IDs are available.
        await db.flush()

        # -------------------------------------------------
        # 5. BARBER SCHEDULES
        # -------------------------------------------------

        service_logger.info("Seeding barber schedules...")

        schedules = []

        for barber in barbers:
            # Every barber works from Monday to Sunday.
            for day in range(7):
                schedules.append(
                    BarberSchedule(
                        barber_id=barber.id,
                        date_of_week=day,
                        start_time=time(8, 0),
                        end_time=time(20, 0),
                        is_off=False,
                    )
                )

        db.add_all(schedules)
        await db.flush()

        # -------------------------------------------------
        # 6. HISTORICAL BOOKINGS
        # -------------------------------------------------

        service_logger.info(
            f"Seeding historical bookings for "
            f"{HISTORICAL_BOOKING_DAYS} days..."
        )

        booking_records = []

        for day_offset in range(1, HISTORICAL_BOOKING_DAYS + 1):

            # All sample bookings are in the past.
            booking_date = date.today() - timedelta(
                days=day_offset
            )

            for customer_index, customer in enumerate(customers):

                # Distribute customers among barbers.
                barber_index = customer_index % BARBER_COUNT
                barber = barbers[barber_index]

                # Each barber receives up to 3 bookings per day.
                # Start times: 09:00, 12:00, 15:00.
                slot_index = customer_index // BARBER_COUNT

                start_hour = 9 + slot_index * 3
                start_time = time(start_hour, 0)

                # Distribute services among bookings.
                service_index = (
                    customer_index + day_offset
                ) % len(active_services)

                service = active_services[service_index]

                end_time = (
                    datetime.combine(
                        booking_date,
                        start_time,
                    )
                    + timedelta(
                        minutes=service.duration_minutes
                    )
                ).time()

                booking = Booking(
                    customer_id=customer.id,
                    barber_id=barber.id,
                    booking_date=booking_date,
                    start_time=start_time,
                    end_time=end_time,
                    total_price=service.price,
                    status=BookingStatus.completed,
                )

                booking_records.append(
                    (booking, service)
                )

        # Insert bookings first to obtain booking IDs.
        bookings = [
            booking
            for booking, _ in booking_records
        ]

        db.add_all(bookings)
        await db.flush()

        # -------------------------------------------------
        # 7. BOOKING SERVICES
        # -------------------------------------------------

        booking_services = [
            BookingService(
                booking_id=booking.id,
                service_id=service.id,
                price_at_booking=service.price,
            )
            for booking, service in booking_records
        ]

        db.add_all(booking_services)

        # -------------------------------------------------
        # 8. COMMIT
        # -------------------------------------------------

        await db.commit()

        service_logger.info(
            "Seeding completed successfully."
        )

        service_logger.info(
            f"""
            Seed summary:
            - Admin: 1
            - Barbers: {len(barbers)}
            - Customers: {len(customers)}
            - Services: {len(services)}
            - Active services: {len(active_services)}
            - Barber schedules: {len(schedules)}
            - Historical bookings: {len(bookings)}
            - Booking services: {len(booking_services)}
            """
        )


def main():
    configure_logging()

    try:
        asyncio.run(seed_data())
    except Exception:
        service_logger.exception("Database seeding failed")
        raise
    finally:
        shutdown_logging()


if __name__ == "__main__":
    main()