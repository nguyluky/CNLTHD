from typing import Optional

from pydantic import BaseModel, ConfigDict
import decimal

from app.schemas.common import FilterParamBase

class ServiceBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: decimal.Decimal
    duration_minutes: int

class ServiceCreateIn(ServiceBase):
    pass

class ServiceUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[decimal.Decimal] = None
    duration_minutes: Optional[int] = None
    is_active: Optional[bool] = None

class ServiceOutForPrivate(ServiceBase):
    id: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class ServiceOutForPublic(ServiceBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

class ServiceFilterParamForPublic(FilterParamBase):
    name: Optional[str] = None
    min_price: Optional[decimal.Decimal] = None
    max_price: Optional[decimal.Decimal] = None
    min_duration_minutes: Optional[int] = None
    max_duration_minutes: Optional[int] = None

class ServiceFilterParamForPrivate(FilterParamBase):
    name: Optional[str] = None
    min_price: Optional[decimal.Decimal] = None
    max_price: Optional[decimal.Decimal] = None
    min_duration_minutes: Optional[int] = None
    max_duration_minutes: Optional[int] = None
    is_active: Optional[bool] = None