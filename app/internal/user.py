from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import User, get_db
from app.dependencies import get_current_active_user
from app.schemas.user import UpdatePasswordIn, UpdateProfileIn, UserOut


router = APIRouter(prefix="/users", tags=["Users"])


@router.get('/me', 
            description="Returns the currently active user's information",
            response_model=UserOut)
async def get_current_user(
    current_user: User = Depends(get_current_active_user),
):
    return UserOut.from_orm(current_user)


@router.put('/me/password',
            description="Changes the current user's password",
            status_code=status.HTTP_204_NO_CONTENT, responses={400: {"description": "Invalid old password"}})
async def update_current_user_password(
    body: UpdatePasswordIn,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change curret user's password.
    - **old_password**: User's current password
    - **new_password**: User's new password
    """
    # verify password
    if not current_user.verify_password(body.old_password):
        raise HTTPException(status_code=400, detail="Old password is invalid")

    current_user.hash_password(body.new_password)
    db.add(current_user)
    await db.commit()

    return {"message": "Password changed successfully"}


@router.patch('/me', 
              description="Changes the current user's profile",
              response_model=UserOut, status_code=status.HTTP_200_OK)
async def update_current_user_profile(
    body: UpdateProfileIn,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change curret user's profile.
    - **full_name**: User's full name
    - **email**: User's email
    - **phone**: User's phone number
    """
    
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