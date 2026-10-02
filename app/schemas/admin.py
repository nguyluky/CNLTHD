from app.core.database import UserRole
from app.schemas.auth import RegisterIn
from app.schemas.common import AllOptionalMeta


class CreateUserIn(RegisterIn):
    role: UserRole


class UserUpdateIn(CreateUserIn, metaclass=AllOptionalMeta):
    pass
