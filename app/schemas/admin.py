from app.core.database import UserRole
from app.schemas.auth import RegisterIn
from app.schemas.common import AllOptionalMeta

from app.schemas.common import FilterParamBase

class GetAllUsersFilterIn(FilterParamBase):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    role: UserRole | None = None

class CreateUserIn(RegisterIn):
    role: UserRole


class UserUpdateIn(CreateUserIn, metaclass=AllOptionalMeta):
    pass
