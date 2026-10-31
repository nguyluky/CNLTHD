"""
tự load router, 
tự cảnh báo lỗi khi chưa handle exception kết thừa tư ApiException
"""


import importlib, os
from typing import Callable

from fastapi import APIRouter
from collections import deque

from app.core.helper import camel_to_upper_snake_case
from app.core.logger import service_logger
from app.schemas.common import create_error_response
from app.core.exception import map_exception as default_map_exception, DomainException

# get all files in the current directory
_files = os.listdir(os.path.dirname(__file__))

_routers: list[APIRouter] = []
# map exception to function that return http response
map_exception: dict[type[Exception], Callable] = default_map_exception.copy()

for file in _files:
    if file.endswith(".py") and file != "__init__.py" and not file.startswith("_"):
        module_name = f"app.routers.{file[:-3]}"
        module = importlib.import_module(module_name)
        if hasattr(module, "router"):
            _routers.append(module.router)
        else:
            service_logger.warning(f"Module {module_name} does not have a 'router' attribute.")

        if hasattr(module, "map_exception"):

            # map_exception.update(module.map_exception)
            for exc_type, handler in module.map_exception.items():
                if exc_type in map_exception:
                    service_logger.warning(f"Exception {exc_type.__name__} is already mapped. Overwriting with new handler from {module_name}.")
                map_exception[exc_type] = handler
        else:
            service_logger.warning(f"Module {module_name} does not have a 'map_exception' attribute.")


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

_all_exceptions = list(_get_all_subclasses(DomainException))
_existing_exceptions = [exc for exc in _all_exceptions if any(exc.__name__ == existing_exc.__name__ for existing_exc in map_exception)]

# kiểm tra xem có tên exception nào trùng nhau không
exception_names = [exc.__name__ for exc in _all_exceptions]
duplicate_exceptions = set(name for name in exception_names if exception_names.count(name) > 1)
if duplicate_exceptions:
    service_logger.warning(f"The error classes have duplicate names: {', '.join(duplicate_exceptions)}. please move to share.py or rename them to avoid confusion.")


# kiểm tra xem có exception nào chưa được handle không
_unhandled_exceptions = [exc for exc in _all_exceptions if exc not in _existing_exceptions]
if _unhandled_exceptions:
    unhandled_exception_names = [exc.__name__ for exc in _unhandled_exceptions]
    service_logger.warning(f"The following error classes are not handled in any router: {', '.join(unhandled_exception_names)}")

router = APIRouter()
for r in _routers:
    router.include_router(r)

def domain_exception_handler(rep, exception: Exception):
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
    "domain_exception_handler",
]