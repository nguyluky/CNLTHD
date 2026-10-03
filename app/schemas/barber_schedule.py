from pydantic import BaseModel, Field, ConfigDict
from datetime import time
from typing import Optional

class BarberScheduleBase(BaseModel):
    date_of_week: int = Field(..., ge=0, le=6)
    start_time: time
    end_time: time
    is_off: bool = False


class BarberScheduleCreateIn(BarberScheduleBase):
    pass


class BarberScheduleUpdateIn(BaseModel):
    date_of_week: int | None = Field(default=None, ge=0, le=6)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_off: Optional[bool] = None


class BarberScheduleOut(BarberScheduleBase):
    id: int
    barber_id: int

    model_config = ConfigDict(from_attributes=True)

class BarberScheduleFilterParam(BaseModel):
    date_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    is_off: Optional[bool] = None
    
    page: int = 1
    limit: int = 10