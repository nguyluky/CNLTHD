import asyncio
from datetime import date, time, timedelta
from decimal import Decimal
from app.core.logger import logger
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
from app.core.config import config


async def reset_database():
    logger.info("Clearing Database...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database cleared")

async def seed_data():
    logger.info(f"Seeding Database: {config.DATABASE_URL}")

    await reset_database()

    async with SessionLocal() as db:
        logger.info("Currently seeding Database...")

        # Services
        services = [
            Service(
                name="Cắt tóc nam tiêu chuẩn",
                description="Cắt tóc, cạo mặt, vuốt sáp",
                price=Decimal("70000.00"),
                duration_minutes=30,
            ),
            Service(
                name="Gội đầu thư giãn",
                description="Gội đầu massage 20 phút",
                price=Decimal("40000.00"),
                duration_minutes=20,
            ),
            Service(
                name="Uốn tóc",
                description="Uốn phồng, uốn xoăn",
                price=Decimal("250000.00"),
                duration_minutes=90,
            ),
        ]
        db.add_all(services)
        await db.flush()

        # Users
        admin = User(
            full_name="System Admin",
            email="admin@salon.com",
            phone="0900000000",
            role=UserRole.admin,
        )
        admin.hash_password("Admin@123")

        barber1 = User(
            full_name="Barber John",
            email="john@salon.com",
            phone="0911111111",
            role=UserRole.barber,
        )
        barber1.hash_password("Barber@123")

        barber2 = User(
            full_name="Barber Wick",
            email="wick@salon.com",
            phone="0922222222",
            role=UserRole.barber,
        )
        barber2.hash_password("Barber@123")

        customer1 = User(
            full_name="Khách Hàng A",
            email="khachhanga@gmail.com",
            phone="0933333333",
            role=UserRole.customer,
        )
        customer1.hash_password("CustomerA@123")
        customer2 = User(
            full_name="Khách Hàng B",
            email="khachhangb@gmail.com",
            phone="0944444444",
            role=UserRole.customer,
        )
        customer2.hash_password("CustomerB@123")

        db.add_all([admin, barber1, barber2, customer1, customer2])
        await db.flush()

        # Schedules
        schedules = []
        # Baber 1 ranges from monday (0) to friday (4)
        for day in range(5):
            schedules.append(
                BarberSchedule(
                    barber_id=barber1.id,
                    date_of_week=day,
                    start_time=time(8, 0),
                    end_time=time(18, 0),
                )
            )

        # Barber 2 ranges from wednesday (2) to sunday (6)
        for day in range(2, 7):
            schedules.append(
                BarberSchedule(
                    barber_id=barber2.id,
                    date_of_week=day,
                    start_time=time(13, 0),
                    end_time=time(21, 0),
                )
            )

        db.add_all(schedules)
        await db.flush()

        # Bookings
        # Customer a scheduled Cắt tóc (70k) + Gội đầu (40k) = 110k
        total_booking_price = services[0].price + services[1].price

        booking1 = Booking(
            customer_id=customer1.id,
            barber_id=barber1.id,
            booking_date=date.today() + timedelta(days=1),
            start_time=time(9, 0),
            end_time=time(9, 50),
            total_price=total_booking_price,
            status=BookingStatus.confirmed,
        )
        db.add(booking1)
        await db.flush()

        # Booking_Service
        booking_services = [
            BookingService(
                booking_id=booking1.id,
                service_id=services[0].id,
                price_at_booking=services[0].price,
            ),
            BookingService(
                booking_id=booking1.id,
                service_id=services[1].id,
                price_at_booking=services[1].price,
            ),
        ]
        db.add_all(booking_services)

        await db.commit()
        logger.info("Seeding finished")


if __name__ == "__main__":
    asyncio.run(seed_data())
