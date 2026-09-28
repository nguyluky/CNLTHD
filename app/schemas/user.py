from typing import Optional
from pydantic import BaseModel, ConfigDict, model_validator
from app.schemas.common import CustomEmailStr, CustomPhoneStr, FullNameStr, PasswordStr


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str
    is_active: bool
    role: str

    model_config = ConfigDict(from_attributes=True)


class UpdateProfileIn(BaseModel):
    full_name: Optional[FullNameStr] = None
    email: Optional[CustomEmailStr] = None
    phone: Optional[CustomPhoneStr] = None


class UpdatePasswordIn(BaseModel):
    old_password: str
    new_password: PasswordStr

    @model_validator(mode="after")
    def verify_password_match(self):
        if self.old_password == self.new_password:
            raise ValueError("New password cannot be the same as the old password")
        return self
