from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import FilterParamBase


class BarberOut(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str
    is_active: bool
    role: str

    model_config = ConfigDict(from_attributes=True)

class BarberFilterParam(FilterParamBase):
    full_name: Optional[str] = Field(
        default=None, description="Filter by barber's full name."
    )
    email: Optional[str] = Field(
        default=None, description="Filter by barber's email."
    )
    phone: Optional[str] = Field(
        default=None, description="Filter by barber's phone."
    )
    is_active: Optional[bool] = Field(
        default=None, description="Filter by active status."
    )

    
        



