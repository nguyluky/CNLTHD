import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from redis_fastapi import CacheBackendDep
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import config
from app.core.database import User, get_db
from app.schemas.auth import LoginOut, RegisterIn, RegisterOut
from app.core.security import get_password_hash
from app.dependencies import EmailServiceDep

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    description="Register a new user",
    response_model=RegisterOut,
    status_code=201,
    responses={409: {"description": "User already exists"}},
)
async def register(
    body: RegisterIn,
    redis: CacheBackendDep,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
    email_service: EmailServiceDep,
):
    """
    Register a new user.
    - **full_name**: Full name of the user
    - **email**: Email address of the user unique
    - **password**: Password for the user account
    - **phone**: Phone number of the user unique
    """

    # check if user already exists
    existing_user = await db.scalar(
        select(User).where(or_(User.email == body.email, User.phone == body.phone))
    )
    if existing_user:
        raise HTTPException(status_code=409, detail="User already exists")

    token = str(uuid.uuid4())

    redis_key = f"register:{token}"

    await redis.set(redis_key, body.model_dump(), ttl=3600, eviction_group="register")

    confirmation_link = f"{config.BASE_URL}/auth/confirm/{token}"
    background_tasks.add_task(
        email_service.send_confirmation_email,
        to=body.email,
        confirmation_link=confirmation_link,
    )

    return {
        "message": "User registered successfully. Please check your email to confirm your registration."
    }


@router.post(
    "/confirm/{token}",
    description="Confirm user registration",
    response_model=RegisterOut,
    status_code=200,
    responses={404: {"description": "Token not found"}},
)
async def confirm_registration(
    token: str, redis: CacheBackendDep, db: AsyncSession = Depends(get_db)
):
    """
    Confirm user registration using the token sent to the user's email.
    - **token**: Token sent to the user's email
    """

    redis_key = f"register:{token}"
    data = await redis.get(redis_key, eviction_group="register")
    await redis.delete(redis_key, eviction_group="register")
    user_data = RegisterIn.model_validate(data) if data else None

    if not user_data:
        raise HTTPException(status_code=404, detail="Token not found or expired")

    # remove password from user_data before creating user
    user = User(**user_data.model_dump(exclude={"password"}))
    user.hash_password(user_data.password)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {"message": "User registered successfully"}


@router.post(
    "/login",
    description="Login with email and password",
    response_model=LoginOut,
    status_code=200,
)
async def login(
    body: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.email == body.username))
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # verify password
    if not user.verify_password(body.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = user.create_access_token(
        timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"message": "Login successful", "email": user.email, "access_token": token}
