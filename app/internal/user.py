from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.database import User
from app.dependencies import get_current_active_user


router = APIRouter(prefix="/users", tags=["Users"])

class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str
    is_active: bool
    role: str

    model_config = ConfigDict(from_attributes=True)



@router.get('/me')
async def get_current_user(
    current_user: "User" = Depends(get_current_active_user)
) -> UserOut:
    return UserOut.from_orm(current_user)