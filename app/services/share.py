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

def create_handle_api_exception(map: dict[type[Exception], Callable]):
    """
    map: dict[type[Exception], Callable] - mapping từ exception type sang callable function return http response
    """
    def handle_api_exception(rep, exception: Exception):
        exception_type = type(exception)
        if exception_type in map:
            http_exception = map[exception_type](str(exception))
            error_code = camel_to_upper_snake_case(exception_type.__name__)
            return create_error_response(
                status_code=http_exception.status_code,
                error_code=error_code,
                message=http_exception.detail,
            )
        
        else: 
            raise exception

    return handle_api_exception
