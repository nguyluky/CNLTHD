"""
tự load router, 
tự cảnh báo lỗi khi chưa handle exception kết thừa tư ApiException
"""


import importlib, os
from typing import Callable

from fastapi import APIRouter, HTTPException
from collections import deque

from app.core.logger import logger
from app.main import create_error_response
from app.services.share import NotFoundException, ServiceException, UserNotFoundException, camel_to_upper_snake_case

# get all files in the current directory
_files = os.listdir(os.path.dirname(__file__))

_routers: list[APIRouter] = []
# map exception to function that return http response
map_exception: dict[type[Exception], Callable] = {
    NotFoundException: lambda msg: HTTPException(status_code=404, detail=msg or "Resource not found"),
    UserNotFoundException: lambda msg: HTTPException(status_code=404, detail=msg or "User not found"),
    
}

for file in _files:
    if file.endswith(".py") and file != "__init__.py" and not file.startswith("_"):
        module_name = f"app.routers.{file[:-3]}"
        module = importlib.import_module(module_name)
        if hasattr(module, "router"):
            _routers.append(module.router)
        else:
            logger.warning(f"Module {module_name} does not have a 'router' attribute.")

        if hasattr(module, "map_exception"):
            map_exception.update(module.map_exception)
        else:
            logger.warning(f"Module {module_name} does not have a 'map_exception' attribute.")


def _get_all_subclasses(cls):
    seen = set()
    # Use a queue to traverse the inheritance tree
    queue = deque(cls.__subclasses__())
    
    while queue:
        subclass = queue.popleft()
        if subclass not in seen:
            seen.add(subclass)
            if not subclass.__name__.startswith("_"): # Ignore private classes
                yield subclass
            # Add this subclass's children to the queue
            queue.extend(subclass.__subclasses__())

_all_exceptions = list(_get_all_subclasses(ServiceException))
_existing_exceptions = [exc for exc in _all_exceptions if any(exc.__name__ == existing_exc.__name__ for existing_exc in map_exception)]

# kiểm tra xem có tên exception nào trùng nhau không
exception_names = [exc.__name__ for exc in _all_exceptions]
duplicate_exceptions = set(name for name in exception_names if exception_names.count(name) > 1)
if duplicate_exceptions:
    logger.warning(f"The error classes have duplicate names: {', '.join(duplicate_exceptions)}. please move to share.py or rename them to avoid confusion.")


# kiểm tra xem có exception nào chưa được handle không
_unhandled_exceptions = [exc for exc in _all_exceptions if exc not in _existing_exceptions]
if _unhandled_exceptions:
    unhandled_exception_names = [exc.__name__ for exc in _unhandled_exceptions]
    logger.warning(f"The following error classes are not handled in any router: {', '.join(unhandled_exception_names)}")

router = APIRouter()
for r in _routers:
    router.include_router(r)

def exception_handler(rep, exception: Exception):
    exception_type = type(exception)
    if exception_type in map_exception:
        http_exception = map_exception[exception_type](str(exception))
        error_code = camel_to_upper_snake_case(exception_type.__name__)
        return create_error_response(
            status_code=http_exception.status_code,
            error_code=error_code,
            message=http_exception.detail,
        )
    
    else: 
        raise exception

__all__ = [
    "router",
    "exception_handler",
]