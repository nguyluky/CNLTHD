from typing import Optional
from pydantic import BaseModel, ConfigDict, model_validator, Field
from app.schemas.common import CustomEmailStr, CustomPhoneStr, SanitizedFullNameStr, PasswordStr


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str
    is_active: bool
    role: str

    model_config = ConfigDict(from_attributes=True)


class UpdateProfileIn(BaseModel):
    full_name: Optional[SanitizedFullNameStr] = Field(
        default=None, description="Updated full name."
    )
    email: Optional[CustomEmailStr] = Field(
        default=None, description="Updated email address."
    )
    phone: Optional[CustomPhoneStr] = Field(
        default=None, description="Updated phone number."
    )


class UpdatePasswordIn(BaseModel):
    old_password: str = Field(..., description="The user's current password.")
    new_password: PasswordStr = Field(
        ..., description="The new password to set (must meet security rules)."
    )

    @model_validator(mode="after")
    def verify_password_match(self):
        if self.old_password == self.new_password:
            raise ValueError("New password cannot be the same as the old password")
        return self
