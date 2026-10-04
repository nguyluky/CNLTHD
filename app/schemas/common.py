from typing import Annotated, Any, Dict, Optional, Tuple
from pydantic import BaseModel, Field
import pydantic
from typing import Annotated, Generic, TypeVar
from pydantic import BaseModel, Field
from app.core.constants import EMAIL_REGEX, PHONE_REGEX
from pydantic._internal._model_construction import ModelMetaclass


CustomEmailStr = Annotated[
    str, Field(pattern=EMAIL_REGEX, examples=["user@example.com"])
]

CustomPhoneStr = Annotated[str, Field(pattern=PHONE_REGEX, examples=["0912345678"])]

FullNameStr = Annotated[str, Field(min_length=3, max_length=100, examples=["John Doe"])]

PasswordStr = Annotated[str, Field(min_length=8, max_length=32)]


class AllOptionalMeta(ModelMetaclass):
    """
    Metaclass to make all fields in a model optional, useful for PATCH requests.
    # https://github.com/pydantic/pydantic/issues/6381#issuecomment-1618214335
    """

    def __new__(
        self, name: str, bases: Tuple[type], namespaces: Dict[str, Any], **kwargs
    ):
        annotations: dict = namespaces.get("__annotations__", {})

        for base in bases:
            for base_ in base.__mro__:
                if base_ is BaseModel:
                    break

                annotations.update(base_.__annotations__)

        for field in annotations:
            if not field.startswith("__"):
                annotations[field] = Optional[annotations[field]]

        namespaces["__annotations__"] = annotations

        return super().__new__(self, name, bases, namespaces, **kwargs)
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
