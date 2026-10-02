import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis_fastapi import CacheBackendDep
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import config
from app.core.database import SessionToken, User, get_db
from app.schemas.auth import (
    DevicesOut,
    LoginOut,
    OAuth2Logout,
    OAuth2Refresh,
    OAuth2Password,
    RegisterIn,
    RegisterOut,
)
from app.core.security import decode_token, hash_sha256
from app.dependencies import DeviceInfoDep, EmailServiceDep, get_current_active_user
from app.core.logger import logger

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
    data: Annotated[OAuth2Password, Depends()],
    device_info: DeviceInfoDep,
    db: AsyncSession = Depends(get_db),
):
    """
    Login with email and password.
    - **grant_type**: Must be "password" for this endpoint
    - **username**: Email address of the user
    - **password**: Password for the user account
    """

    user = await db.scalar(select(User).where(User.email == data.username))
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # verify password
    if not user.verify_password(data.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")


    refresh_token_expires_delta = timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)

    refresh_token = str(uuid.uuid4())

    # hash SHA256
    refresh_token_hash = hash_sha256(refresh_token)

    session_token = SessionToken(
        user_id=user.id,
        refresh_token_hash=refresh_token_hash,
        device_id=device_info.device_id,
        device_name=device_info.device_name,
        device_type=device_info.device_type,
        os=device_info.os,
        browser=device_info.browser,
        ip_address=device_info.ip_address,
        user_agent=device_info.user_agent,
        expired_at=datetime.now(timezone.utc) + refresh_token_expires_delta,
    )

    db.add(session_token)
    await db.commit()
    await db.refresh(session_token)

    access_token = user.create_access_token(
        timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES),
        sid=f"session_{session_token.id}"
    ) 

    return {
        "message": "Login successful",
        "email": user.email,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


@router.post(
    "/refresh",
    description="Refresh access token using refresh token",
    response_model=LoginOut,
    status_code=200,
)
async def refresh_token(
    data: Annotated[OAuth2Refresh, Depends()], db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token.
    - **grant_type**: Must be "refresh_token" for this endpoint
    - **refresh_token**: Refresh token obtained during login
    - **client_id**: The client ID
    - **client_secret**: The client secret
    """

    hash_refresh_token = hash_sha256(data.refresh_token)

    session_token = await db.scalar(
        select(SessionToken)
        .where(SessionToken.refresh_token_hash == hash_refresh_token)
        .options(joinedload(SessionToken.user))
    )

    if not session_token:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    if session_token.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    refresh_token_expires_delta = timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)

    new_refresh_token = str(uuid.uuid4())

    new_refresh_token_hash = hash_sha256(new_refresh_token)

    session_token.refresh_token_hash = new_refresh_token_hash
    session_token.expired_at = datetime.now(timezone.utc) + refresh_token_expires_delta
    session_token.last_activity_at = datetime.now(timezone.utc)

    db.add(session_token)
    await db.commit()
    await db.refresh(session_token)
    
    new_access_token = session_token.user.create_access_token(
        timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES),
        sid=f"session_{session_token.id}"
    )

    return {
        "message": "Token refreshed successfully",
        "email": session_token.user.email,
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
    }

@router.post(
    "/logout",
    description="Logout and revoke refresh token",
    status_code=200,
)
async def logout(
    data: Annotated[OAuth2Logout, Depends()], db: AsyncSession = Depends(get_db)
):
    """
    Logout and revoke refresh token.
    - **refresh_token**: Refresh token obtained during login
    - **client_id**: The client ID
    - **client_secret**: The client secret
    """

    hash_refresh_token = hash_sha256(data.refresh_token)

    session_token = await db.scalar(
        select(SessionToken)
        .where(SessionToken.refresh_token_hash == hash_refresh_token)
    )

    if not session_token:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    if session_token.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    session_token.revoked_at = datetime.now(timezone.utc)

    db.add(session_token)
    await db.commit()

    return {
        "message": "Logout successful",
    }

@router.post(
    "/logout_all",
    description="Logout from all devices and revoke all refresh tokens",
    status_code=200,
)
async def logout_all(
    data: Annotated[OAuth2Logout, Depends()], db: AsyncSession = Depends(get_db)
):
    """
    Logout from all devices and revoke all refresh tokens.
    - **refresh_token**: Refresh token obtained during login
    - **client_id**: The client ID
    - **client_secret**: The client secret
    """

    hash_refresh_token = hash_sha256(data.refresh_token)

    session_token = await db.scalar(
        select(SessionToken)
        .where(SessionToken.refresh_token_hash == hash_refresh_token)
        .options(joinedload(SessionToken.user))
    )

    if not session_token:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    if session_token.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    user_id = session_token.user_id

    query = update(SessionToken).where(SessionToken.user_id == user_id).values(revoked_at=datetime.now(timezone.utc))

    # Revoke all refresh tokens for the user
    await db.execute( query)
    await db.commit()

    return {
        "message": "Logout from all devices successful",
    }

@router.get(
    "/devices",
    description="Get all active devices for the current user",
    response_model=list[DevicesOut],
    status_code=200,
)
async def get_active_devices(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """
    Get all active devices for the current user.
    """

    active_devices = await db.scalars(
        select(SessionToken)
        .where(SessionToken.user_id == current_user.id)
        .where(SessionToken.revoked_at.is_(None))
    )

    return {
        "message": "Active devices retrieved successfully",
        "active_devices": active_devices.all(),
    }

@router.post(
    "/forgot_password",
    description="Request password reset",
    status_code=200,
)
async def forgot_password(
    email: str,
    redis: CacheBackendDep,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
    email_service: EmailServiceDep,
):
    """
    Request password reset.
    - **email**: Email address of the user
    """

    user = await db.scalar(select(User).where(User.email == email))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = str(uuid.uuid4())
    redis_key = f"forgot_password:{token}"

    await redis.set(redis_key, {"user_id": user.id}, ttl=3600, eviction_group="forgot_password")

    reset_link = f"{config.BASE_URL}/auth/reset_password/{token}"
    background_tasks.add_task(
        email_service.send_reset_password_email,
        to=email,
        reset_link=reset_link,
    )

    return {
        "message": "Password reset link sent. Please check your email.",
    }

@router.post(
    "/reset_password/{token}",
    description="Reset password using token",
    status_code=200,
)
async def reset_password(
    token: str,
    new_password: str,
    redis: CacheBackendDep,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Reset password using token.
    - **token**: Token sent to the user's email
    - **new_password**: New password for the user account
    """

    redis_key = f"forgot_password:{token}"
    data = await redis.get(redis_key, eviction_group="forgot_password")
    await redis.delete(redis_key, eviction_group="forgot_password")

    if not data:
        raise HTTPException(status_code=404, detail="Token not found or expired")

    user_id = data.get("user_id")
    user = await db.scalar(select(User).where(User.id == user_id))

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hash_password(new_password)
    await db.commit()
    await db.refresh(user)

    return {
        "message": "Password reset successful",
    }
