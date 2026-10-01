from pydantic import BaseModel
from app.schemas.common import CustomEmailStr, CustomPhoneStr, FullNameStr, PasswordStr


class RegisterIn(BaseModel):
    full_name: FullNameStr
    email: CustomEmailStr
    password: PasswordStr
    phone: CustomPhoneStr


class RegisterOut(BaseModel):
    message: str


class LoginOut(BaseModel):
    message: str
    email: str
    access_token: str
    token_type: str = "bearer"
