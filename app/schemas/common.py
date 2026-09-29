from typing import Annotated
from pydantic import Field
from app.core.constants import EMAIL_REGEX, PHONE_REGEX


CustomEmailStr = Annotated[
    str,
    Field(pattern=EMAIL_REGEX, examples=["user@example.com"])
]

CustomPhoneStr = Annotated[
    str,
    Field(pattern=PHONE_REGEX, examples=["0912345678"])
]

FullNameStr = Annotated[
    str,
    Field(min_length=3, max_length=100, examples=["John Doe"])
]

PasswordStr = Annotated[
    str,
    Field(min_length=8, max_length=32)
]