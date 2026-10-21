from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
import decimal

from app.schemas.common import FilterParamBase

class ServiceBase(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="The name of the service (e.g., 'Classic Haircut').",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="A detailed description of what the service includes.",
    )
    price: decimal.Decimal = Field(
        ...,
        ge=decimal.Decimal("0.00"),
        description="The cost of the service (must be zero or greater).",
    )
    duration_minutes: int = Field(
        ...,
        gt=0,
        description="The estimated duration of the service in minutes (must be greater than 0)."
    )

class ServiceCreateIn(ServiceBase):
    pass

class ServiceUpdateIn(BaseModel):
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Updated name of the service.",
    )
    description: Optional[str] = Field(
        default=None, max_length=500, description="Updated service description."
    )
    price: Optional[decimal.Decimal] = Field(
        default=None,
        ge=decimal.Decimal("0.00"),
        description="Updated price of the service.",
    )
    duration_minutes: Optional[int] = Field(
        default=None,
        gt=0,
        description="Updated duration in minutes.",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Updated active status of the service.",
    )

class ServiceOutForPrivate(ServiceBase):
    id: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class ServiceOutForPublic(ServiceBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

class ServiceFilterParamForPublic(FilterParamBase):
    name: Optional[str] = Field(
        default=None, description="Filter services containing this name."
    )
    min_price: Optional[decimal.Decimal] = Field(
        default=None,
        description="Minimum price filter.",
    )
    max_price: Optional[decimal.Decimal] = Field(
        default=None,
        description="Maximum price filter.",
    )
    min_duration_minutes: Optional[int] = Field(
        default=None, description="Minimum duration filter in minutes."
    )
    max_duration_minutes: Optional[int] = Field(
        default=None, description="Maximum duration filter in minutes."
    )

class ServiceFilterParamForPrivate(FilterParamBase):
    name: Optional[str] = Field(
        default=None, description="Filter services containing this name."
    )
    min_price: Optional[decimal.Decimal] = Field(
        default=None,
        description="Minimum price filter.",
    )
    max_price: Optional[decimal.Decimal] = Field(
        default=None,
        description="Maximum price filter.",
    )
    min_duration_minutes: Optional[int] = Field(
        default=None, description="Minimum duration filter in minutes."
    )
    max_duration_minutes: Optional[int] = Field(
        default=None, description="Maximum duration filter in minutes."
    )
    is_active: Optional[bool] = Field(
        default=None, description="Filter by active status."
    )