from typing import Optional

from pydantic import BaseModel, ConfigDict
from decimal import Decimal

from app.routers.admin import MakeOptional
from app.schemas.common import FilterParamBase, SanitizedDescriptionStr, SanitizedNameStr

class ServiceBase(BaseModel):
    name: SanitizedNameStr
    description: Optional[SanitizedDescriptionStr] = None
    price: Decimal
    duration_minutes: int

class ServiceCreateIn(ServiceBase):
    pass

class ServiceUpdateIn(BaseModel):
    name: Optional[SanitizedNameStr] = None
    description: Optional[SanitizedDescriptionStr] = None
    price: Optional[Decimal] = None
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
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    min_duration_minutes: Optional[int] = None
    max_duration_minutes: Optional[int] = None

class ServiceFilterParamForPrivate(ServiceFilterParamForPublic):
    is_active: Optional[bool] = None