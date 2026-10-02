from pydantic import BaseModel


class ErrorModel(BaseModel):
    error_code: str
    message: str


class ValidationErrorModel(ErrorModel):
    details: list[dict] | None = None


class NotFoundException(Exception):
    pass


class RequestedServiceForBookingNotFound(Exception):
    pass
