from fastapi import HTTPException


class DomainException(Exception):
    """Base class for API exceptions."""

    def __init__(self, message: str | None = None):
        self.message = message

class NotFoundException(DomainException):
    """Exception raised when a requested resource is not found."""
    # sử dụng ở tần router
    pass

class UserNotFoundException(DomainException):
    pass


class NotAllowedException(DomainException):
    """Exception raised when a user is not allowed to perform an action."""
    pass


map_exception ={
    NotFoundException: lambda msg: HTTPException(status_code=404, detail=msg or "Resource not found"),
    UserNotFoundException: lambda msg: HTTPException(status_code=404, detail=msg or "User not found"),
    NotAllowedException: lambda msg: HTTPException(status_code=403, detail=msg or "Not allowed"),
}