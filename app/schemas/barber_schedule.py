from pydantic import BaseModel, Field, ConfigDict, model_validator
from datetime import date, time
from typing import Optional

from app.schemas.common import FilterParamBase

class BarberScheduleBase(BaseModel):
    date_of_week: int = Field(
        ..., 
        ge=0, 
        le=6,
        description="Day of the week (0 = Monday, 6 = Sunday, following standard Python conventions)."
    )
    start_time: time = Field(..., description="The start time of the barber's shift.")
    end_time: time = Field(..., description="The end time of the barber's shift.")
    is_off: bool = Field(
        default=False,
        description="Flag indicating if the barber is off on this day.",
    )

    @model_validator(mode="after")
    def validate_shift_times(self) -> "BarberScheduleBase":
        # Ensure start time is before end time if the barber is working
        if not self.is_off and self.start_time >= self.end_time:
            raise ValueError("start_time must be strictly earlier than end_time.")
        return self


class BarberScheduleCreateIn(BarberScheduleBase):
    pass


class BarberScheduleUpdateIn(BaseModel):
    date_of_week: Optional[int] = Field(
        default=None,
        ge=0,
        le=6,
        description="Updated day of the week (0 to 6).",
    )
    start_time: Optional[time] = Field(
        default=None, description="Updated start time of the shift."
    )
    end_time: Optional[time] = Field(
        default=None, description="Updated end time of the shift."
    )
    is_off: Optional[bool] = Field(
        default=None, description="Updated off-status flag."
    )

    @model_validator(mode="after")
    def validate_shift_times(self) -> "BarberScheduleUpdateIn":
        # If both are provided in the patch/update payload, validate their relationship
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.start_time >= self.end_time
        ):
            raise ValueError("start_time must be strictly earlier than end_time.")
        return self


class BarberScheduleOut(BarberScheduleBase):
    id: int
    barber_id: int

    model_config = ConfigDict(from_attributes=True)

class BarberScheduleFilterParam(FilterParamBase):
    date_of_week: Optional[int] = Field(
        default=None,
        description="Filter by day of the week (0 = Monday, 6 = Sunday).",
    )
    is_off: Optional[bool] = Field(
        default=None, description="Filter by whether the barber is off."
    )

class TimeSlotSchema(BaseModel):
    start_time: time
    end_time: time

class AvailableSlotOut(BaseModel):
    booking_date: date
    slot_duration_minutes: int
    available_slots: list[TimeSlotSchema]