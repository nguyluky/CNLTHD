from typing import Optional
from pydantic import BaseModel, ConfigDict, model_validator


class BarberOut(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str
    is_active: bool
    role: str

    model_config = ConfigDict(from_attributes=True)

class BarberFilterParam(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None

    page: int = 1
    limit: int = 10
    
        



