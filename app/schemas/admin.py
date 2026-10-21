from typing import Optional

from app.core.database import UserRole
from app.schemas.auth import RegisterIn
from app.schemas.common import MakeOptional
from pydantic import Field
from app.schemas.common import FilterParamBase

class GetAllUsersFilterIn(FilterParamBase):
    full_name: Optional[str] = Field(
        default=None, description="Filter by user's full name (partial match)."
    )
    email: Optional[str] = Field(
        default=None, description="Filter by email address."
    )
    phone: Optional[str] = Field(
        default=None, description="Filter by phone number."
    )
    role: Optional[UserRole] = Field(
        default=None, description="Filter by user role."
    )

class CreateUserIn(RegisterIn):
    role: UserRole



class UserUpdateIn(CreateUserIn, MakeOptional):
    pass
