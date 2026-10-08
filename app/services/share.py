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
    """
    Khi người dùng không có quyền truy cập vào barber schedule.
    admin hoặc chính barber mới có quyền truy cập.
    """

    pass