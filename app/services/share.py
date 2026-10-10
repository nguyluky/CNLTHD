"""
Chứa những thứ có thể dùng chung giữa các service khác nhau, ví dụ như các exception dùng chung.

"""


from typing import Callable
import collections

from app.core.helper import camel_to_upper_snake_case
from app.schemas.common import create_error_response


class ServiceException(Exception):
    """Base class for API exceptions."""

    def __init__(self, message: str | None = None):
        self.message = message

class NotFoundException(ServiceException):
    """Exception raised when a requested resource is not found."""
    pass

class UserNotFoundException(ServiceException):
    pass


class NotAllowedException(ServiceException):
    """Exception raised when a user is not allowed to perform an action."""
    pass