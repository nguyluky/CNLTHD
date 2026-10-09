from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import User, get_db
from app.dependencies import get_current_active_user
from app.schemas.user import UpdatePasswordIn, UpdateProfileIn, UserOut
from app.services.user_service import EmailExistsException, InvalidOldPasswordException, PhoneExistsException, UserServiceDep


router = APIRouter(
    prefix="/users", 
    tags=["Users"]
)


@router.get(
    "/me",
    description="Returns the currently active user's information",
    response_model=UserOut,
    status_code=status.HTTP_200_OK,
)
async def get_current_user(
    current_user: User = Depends(get_current_active_user),
):
    return current_user


@router.put(
    "/me/password",
    description="Changes the current user's password",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={400: {"description": "Invalid old password"}},
)
async def update_current_user_password(
    body: UpdatePasswordIn,
    user_service: UserServiceDep,
    current_user: User = Depends(get_current_active_user),
):
    """
    Change curret user's password.
    - **old_password**: User's current password
    - **new_password**: User's new password
    """
    await user_service.update_current_user_password(
        current_user=current_user,
        old_password=body.old_password,
        new_password=body.new_password,
    )
    


@router.patch(
    "/me",
    description="Changes the current user's profile",
    response_model=UserOut,
    status_code=status.HTTP_200_OK,
)
async def update_current_user_profile(
    body: UpdateProfileIn,
    user_service: UserServiceDep,
    current_user: User = Depends(get_current_active_user),
):
    """
    Change curret user's profile.
    - **full_name**: User's full name
    - **email**: User's email
    - **phone**: User's phone number
    """

    update_data = body.model_dump(exclude_unset=True)

    current_user = await user_service.update_current_user_profile(
        current_user=current_user,
        update_data=update_data
    )

    return current_user

map_exception = {
    InvalidOldPasswordException: lambda e: HTTPException(
        status_code=400, detail=e or "Old password is invalid"
    ),
    PhoneExistsException: lambda e: HTTPException(
        status_code=409, detail=e or "This phone number is currently being used by a different user"
    ),
    EmailExistsException: lambda e: HTTPException(
        status_code=409, detail=e or "This email is currently being used by a different user"
    ),
        
}
