from datetime import datetime
from enum import Enum as PyEnum
from typing_extensions import Annotated

from fastapi import Form
from fastapi.security import OAuth2PasswordRequestForm
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
    refresh_token: str
    token_type: str = "bearer"


class GrantType(str, PyEnum):
    PASSWORD = "password"
    REFRESH_TOKEN = "refresh_token"


class _OAuth2PasswordAndRefreshRequestForm(OAuth2PasswordRequestForm):
    """Modified from fastapi.security.OAuth2PasswordRequestForm"""

    def __init__(
        self,
        grant_type: Annotated[GrantType, Form()] = GrantType.PASSWORD,
        username: str = Form(default=""),
        password: str = Form(default=""),
        refresh_token: str = Form(default=""),
        client_id: str | None = Form(default=None),
        client_secret: str | None = Form(default=None),
    ):
        super().__init__(
            grant_type=grant_type,
            username=username,
            password=password,
            client_id=client_id,
            client_secret=client_secret,
        )
        self.refresh_token = refresh_token


class OAuth2Password(_OAuth2PasswordAndRefreshRequestForm):
    """Modified from fastapi.security.OAuth2PasswordRequestForm"""

    def __init__(
        self,
        username: str = Form(default=""),
        password: str = Form(default=""),
        scope: str = Form(default=""),
        client_id: str | None = Form(default=None),
        client_secret: str | None = Form(default=None),
    ):
        super().__init__(
            grant_type=GrantType.PASSWORD,
            username=username,
            password=password,
            client_id=client_id,
            client_secret=client_secret,
        )
        self.scopes = scope.split()


class OAuth2Refresh(_OAuth2PasswordAndRefreshRequestForm):
    """Modified from fastapi.security.OAuth2PasswordRequestForm"""

    def __init__(
        self,
        refresh_token: str = Form(default=""),
        scope: str = Form(default=""),
        client_id: str | None = Form(default=None),
        client_secret: str | None = Form(default=None),
    ):
        super().__init__(
            grant_type=GrantType.REFRESH_TOKEN,
            refresh_token=refresh_token,
            username="",
            password="",
            client_id=client_id,
            client_secret=client_secret,
        )
        self.scopes = scope.split()
        self.refresh_token = refresh_token



class OAuth2Logout(OAuth2Refresh):
    """Modified from fastapi.security.OAuth2PasswordRequestForm"""


class Device(BaseModel):
    device_id: str
    device_name: str | None
    device_type: str | None
    os: str | None
    browser: str | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
    last_activity_at: datetime
    expired_at: datetime
    revoked_at: datetime | None

class DevicesOut(BaseModel):
    message: str
    active_devices: list[Device]