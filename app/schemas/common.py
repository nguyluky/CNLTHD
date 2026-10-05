from typing import Annotated, Any, Sequence
from fastapi.responses import JSONResponse
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

def create_page_response(items: Sequence[T], total: int, page: int, size: int):
    pages = (total + size - 1) // size  # Calculate total pages
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages
    }

class FilterParamBase(BaseModel):
    page: int = Field(1, ge=1, description="Page number")
    limit: int = Field(10, ge=1, le=100, description="Number of items per page")


class ErrorModel(BaseModel):
    error_code: str
    message: str


class ValidationErrorModel(ErrorModel):
    details: list[dict] | None = None

def create_error_response(status_code: int, error_code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": error_code,
            "message": message
        }
    )

def create_validation_error_response(status_code: int, error_code: str, message: str, details: list[dict] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": error_code,
            "message": message,
            "details": details
        }
    )

class MakeOptional(BaseModel):
    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        for field in cls.model_fields.values():
            # If the field does not have a default value, make it default to None
            if field.is_required():
                field.default = None
        cls.model_rebuild(force=True)
