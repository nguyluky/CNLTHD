from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import User, get_db
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


# # Email: text/number/special + @ + domain + .extension
# EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

# # Phone: 10 digits long and starts with 0
# PHONE_REGEX = r"^0[3|5|7|8|9][0-9]{8}$"

class UpdateProfileIn(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

class UpdatePasswordIn(BaseModel):
    old_password: str
    new_password: str

    @model_validator(mode="after")
    def verify_password_match(self):
        if self.old_password == self.new_password:
            raise ValueError("New password cannot be the same as the old password")
        return self

@router.get('/me')
async def get_current_user(
    current_user: "User" = Depends(get_current_active_user)
) -> UserOut:
    return UserOut.from_orm(current_user)

@router.put('/me/password', status_code=status.HTTP_204_NO_CONTENT, responses={400: {"description": "Invalid old password"}})
async def update_current_user_password(
    body: UpdatePasswordIn,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    # verify password
    if not current_user.verify_password(body.old_password):
        raise HTTPException(status_code=400, detail="Old password is invalid")

    current_user.hash_password(body.new_password)
    db.add(current_user)
    await db.commit()

    return {"message": "Password changed successfully"}

@router.patch('/me', response_model=UserOut, status_code=status.HTTP_200_OK)
async def update_current_user_profile(
    body: UpdateProfileIn,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    update_data = body.model_dump(exclude_unset=True)

    if not update_data:
        return current_user

    if "phone" in update_data:
        phone_exists = await db.scalar(select(User).where(
                User.phone == update_data["phone"]
            )
        )

        if phone_exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This phone number is currently being used by a different user"
            )

        current_user.phone = update_data["phone"]
        
    if "email" in update_data:
        email_exists = await db.scalar(select(User).where(
                User.email == update_data["email"]
            )
        )

        if email_exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is currently being used by a different user"
            )

        current_user.phone = update_data["email"]

    if "full_name" in update_data:
        current_user.full_name = update_data["full_name"]

    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    return current_user