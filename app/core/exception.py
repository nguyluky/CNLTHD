from fastapi.responses import JSONResponse
from pydantic import BaseModel




class NotFoundException(Exception):
    pass


class RequestedServiceForBookingNotFound(Exception):
    pass
