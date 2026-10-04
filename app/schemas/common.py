from typing import Annotated, Generic, TypeVar
from pydantic import BaseModel, Field
from app.core.constants import EMAIL_REGEX, PHONE_REGEX


CustomEmailStr = Annotated[
    str, Field(pattern=EMAIL_REGEX, examples=["user@example.com"])
]

CustomPhoneStr = Annotated[str, Field(pattern=PHONE_REGEX, examples=["0912345678"])]

FullNameStr = Annotated[str, Field(min_length=3, max_length=100, examples=["John Doe"])]

PasswordStr = Annotated[str, Field(min_length=8, max_length=32)]

# Reusable generic PageResponse 
T=TypeVar("T")

class PageResponse(BaseModel, Generic[T]):
    items: list[T] = Field(..., description="List of items on the current page")
    total: int = Field(..., ge=0, description="Total amount of items")
    page: int = Field(..., ge=1, description="Current page")
    size: int = Field(..., ge=1, description="Amount of items on the current page")
    pages: int = Field(..., ge=0, description="Total amount of pages")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "items": [],
                    "total": 42,
                    "page": 1,
                    "size": 10,
                    "pages": 5
                }
            ]
        }
    }

class FilterParamBase(BaseModel):
    page: int = Field(1, ge=1, description="Page number")
    limit: int = Field(10, ge=1, le=100, description="Number of items per page")
