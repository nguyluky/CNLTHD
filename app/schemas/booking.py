from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.database import BookingStatus

class BookingFilterParam(BaseModel):
    booking_date: Optional[date] = None
    status: Optional[BookingStatus] = None
    barber_id: Optional[int] = None
    customer_id: Optional[int] = None
    page: int = 1
    limit: int = 10

class BookingStatusIn(BaseModel):
    status: BookingStatus

class BookingScheduleIn(BaseModel):
    booking_date: Optional[date] = None
    start_time: Optional[time] = None

    @field_validator("booking_date")
    @classmethod
    def validate_booking_date(cls, v: date) -> date:
        if v < date.today():
            raise ValueError("booking date can not be from the past")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "booking_date": "2026-10-01",
                    "start_time": "14:00:00",
                }
            ]
        }
    }
    
class BookingCreateIn(BaseModel):
    barber_id: int = Field(..., description="barber's id")
    booking_date: date = Field(..., description="booking date(YYYY-MM-DD)")
    start_time: time = Field(..., description="booking starts at")
    service_ids: list[int] = Field(..., min_length=1,  description="list of seleted service's ids")

    @field_validator("booking_date")
    @classmethod
    def validate_booking_date(cls, v: date) -> date:
        if v < date.today():
            raise ValueError("booking date can not be from the past")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "barber_id": 1,
                    "booking_date": "2026-10-01",
                    "start_time": "14:00:00",
                    "service_ids": [1, 2]
                }
            ]
        }
    }


class BookingOut(BaseModel):
    id: int
    customer_id: int
    barber_id: int
    booking_date: date
    start_time: time
    end_time: time
    total_price: Decimal = Field(..., ge=0, max_digits=10, decimal_places=2)
    status: BookingStatus

    model_config = ConfigDict(from_attributes=True)
    model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "id": 1,
                        "customer_id": 1,
                        "barber_id": 1,
                        "booking_date": "2026-10-01",
                        "start_time": "14:00:00",
                        "end_time": "14:50:00",
                        "total_price": 110000,
                        "status": "pending",
                    }
                ]
            }
        }

