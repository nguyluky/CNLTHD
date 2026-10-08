

from fastapi.responses import JSONResponse
from pydantic import BaseModel


# TODO: move to share.py

class ApiException(Exception):
    """Base class for API exceptions."""

    def __init__(self, message: str | None = None):
        self.message = message

class NotFoundException(ApiException):
    pass


class RequestedServiceForBookingNotFound(Exception):
    pass
