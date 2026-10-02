from typing import Optional

from pydantic import BaseModel, ConfigDict
import decimal

class ServiceBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: decimal.Decimal
    duration_minutes: int

class ServiceCreate(ServiceBase):
    pass

class ServiceUpdate(ServiceBase):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[decimal.Decimal] = None
    duration_minutes: Optional[int] = None
    is_active: Optional[bool] = None

class ServiceResponse(ServiceBase):
    id: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)