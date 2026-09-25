from collections.abc import AsyncGenerator
from datetime import datetime, time, date, timedelta
from decimal import Decimal
from enum import Enum as PyEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from app.core.security import create_access_token

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, String, Time, UniqueConstraint, func, Numeric, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import DATABASE_URL
from app.core.security import get_password_hash, verify_password

# Preserve existing URLs while selecting an async-capable driver.
database_url = make_url(DATABASE_URL)
if database_url.drivername in {"sqlite", "sqlite+pysqlite"}:
    database_url = database_url.set(drivername="sqlite+aiosqlite")
elif database_url.drivername in {"postgresql", "postgresql+psycopg2"}:
    database_url = database_url.set(drivername="postgresql+psycopg")

engine = create_async_engine(database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as db:
        yield db


class Base(DeclarativeBase):
    pass


# models

class UserRole(str, PyEnum):
    admin = "admin"
    customer = "customer"
    barber = "barber"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String((255)), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), nullable=False, default=UserRole.customer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)

    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    schedules: Mapped[list["BarberSchedule"]] = relationship(
        back_populates="barber",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, full_name='{self.full_name}', email='{self.email}', role='{self.role.name}', created_at='{self.created_at}')>"

    def verify_password(self, password: str) -> bool:
        return verify_password(password, self.hashed_password)
    
    def hash_password(self, password: str) -> None:
        self.hashed_password = get_password_hash(password)
    
    def create_access_token(self, expires_delta: timedelta | None = None) -> str:
        return create_access_token(data={"sub": self.email, "role": self.role.name}, expires_delta=expires_delta)
    
    def is_admin(self) -> bool:
        return self.role == UserRole.admin
    
    def is_customer(self) -> bool:
        return self.role == UserRole.customer

    def is_barber(self) -> bool:
        return self.role == UserRole.barber

class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(nullable=False)

    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<Service(id={self.id}, name='{self.name}', description='{self.description}', price={self.price}, duration_minutes={self.duration_minutes})>"


class BarberSchedule(Base):
    __tablename__ = "barber_schedules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    barber_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date_of_week: Mapped[int] = mapped_column(nullable=False)  # 0=Monday, 6=Sunday
    start_time: Mapped[time] = mapped_column(Time(timezone=True), nullable=False)
    end_time: Mapped[time] = mapped_column(Time(timezone=True), nullable=False)

    is_off: Mapped[bool] = mapped_column(nullable=False, default=False)

    barber: Mapped["User"] = relationship("User", back_populates="schedules")

    def __repr__(self) -> str:
        return f"<BarberSchedule(id={self.id}, barber_id={self.barber_id}, start_time='{self.start_time}', end_time='{self.end_time}')>"


class BookingStatus(str, PyEnum):
    pending = "pending"
    confirmed = "confirmed"
    completed = "completed"
    cancelled = "cancelled"

class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    barber_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    booking_date: Mapped[date] = mapped_column(Date(), nullable=False)

    start_time: Mapped[time] = mapped_column(Time(timezone=True), nullable=False)
    end_time: Mapped[time] = mapped_column(Time(timezone=True), nullable=False)

    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[BookingStatus] = mapped_column(Enum(BookingStatus), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())

    customer: Mapped["User"] = relationship("User", foreign_keys=[customer_id], backref="customer_bookings")
    barber: Mapped["User"] = relationship("User", foreign_keys=[barber_id], backref="barber_bookings")
    services: Mapped[list["BookingService"]] = relationship(back_populates="booking", cascade="all, delete-orphan")

    __table_args__ = (
        # index barber_id and booking_date for faster queries
        Index("ix_bookings_barber_id_booking_date", "barber_id", "booking_date"),
    )

    def __repr__(self) -> str:
        return f"<Booking(id={self.id}, customer_id={self.customer_id}, barber_id={self.barber_id}, booking_date='{self.booking_date}', start_time='{self.start_time}', end_time='{self.end_time}', total_price={self.total_price}, status='{self.status.name}', created_at='{self.created_at}')>"

class BookingService(Base):
    __tablename__ = "booking_services"


    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"), nullable=False)
    price_at_booking: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    booking: Mapped["Booking"] = relationship("Booking", back_populates="services")
    service: Mapped["Service"] = relationship("Service", backref="booking_services")

    __table_args__ = (
        # Ensure that a service can only be added once per booking
        UniqueConstraint("booking_id", "service_id", name="uix_booking_service"),
    )

    def __repr__(self) -> str:
        return f"<BookingService(id={self.id}, booking_id={self.booking_id}, service_id={self.service_id})>"