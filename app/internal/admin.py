from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import User, get_db
from app.dependencies import get_current_active_admin
from app.schemas.user import UserOut
from app.schemas.admin import *


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    responses={
        # không phải là admin thì trả về 403
        403: {"description": "Not enough permissions"}
    },
    # default=Depends(get_current_active_admin)
    dependencies=[Depends(get_current_active_admin)],
)


@router.get("/users", description="Get all users", response_model=list[UserOut])
async def get_all_users(db: Annotated[AsyncSession, Depends(get_db)]):
    # TODO: có thêm filter

    users = await db.scalars(select(User))
    return users.all()


@router.post(
    "/users", description="Create a new user", status_code=201, response_model=UserOut
)
async def create_user(user: CreateUserIn, db: Annotated[AsyncSession, Depends(get_db)]):
    # check if email or phone already exists
    existing_user = await db.scalar(
        select(User).where((User.email == user.email) | (User.phone == user.phone))
    )
    if existing_user:
        raise HTTPException(status_code=400, detail="Email or phone already registered")

    new_user = User(
        full_name=user.full_name, email=user.email, phone=user.phone, role=user.role
    )
    new_user.hash_password(user.password)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.patch("/users/{user_id}", description="Update a user", response_model=UserOut)
async def update_user(
    user_id: int,
    user_update: UserUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # check if email or phone already exists for other users
    existing_user = await db.scalar(
        select(User).where(
            ((User.email == user_update.email) | (User.phone == user_update.phone))
            & (User.id != user_id)
        )
    )
    if existing_user:
        raise HTTPException(status_code=400, detail="Email or phone already registered")

    for field, value in user_update.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    if "password" in user_update.model_dump(exclude_unset=True):
        user.hash_password(user_update.password)

    await db.commit()
    await db.refresh(user)
    return user
