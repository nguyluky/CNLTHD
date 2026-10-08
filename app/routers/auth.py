import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
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
from app.core.helper import camel_to_upper_snake_case
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
from app.dependencies import EmailServiceDep, get_current_active_user
from app.core.logger import logger
from app.schemas.common import create_error_response
from app.services.auth_service import *
    
router = APIRouter(prefix="/auth", tags=["Authentication"])



@router.post(
    "/register",
    description="Register a new user",
    response_model=RegisterOut,
    status_code=201,
    responses={409: {"description": "User already exists"}},
)
async def initialize_user_registration(
    body: RegisterIn,
    background_tasks: BackgroundTasks,
    email_service: EmailServiceDep,
    auth_service: AuthServiceDep,
):
    """
    Register a new user.
    - **full_name**: Full name of the user
    - **email**: Email address of the user unique
    - **password**: Password for the user account
    - **phone**: Phone number of the user unique

    """

    token = await auth_service.initialize_user_registration(
        full_name=body.full_name,
        email=body.email,
        password=body.password,
        phone=body.phone,
    )

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
async def confirm_registration(token: str, auth_service: AuthServiceDep):
    """
    Confirm user registration using the token sent to the user's email.
    - **token**: Token sent to the user's email
    """

    await auth_service.confirm_user_registration(token=token)

    return {"message": "User registered successfully"}


@router.post(
    "/login",
    description="Login with email and password",
    response_model=LoginOut,
    status_code=200,
)
async def login(
    data: Annotated[OAuth2Password, Depends()],
    auth_service: AuthServiceDep,
):
    """
    Login with email and password.
    - **grant_type**: Must be "password" for this endpoint
    - **username**: Email address of the user
    - **password**: Password for the user account
    """

    user = await auth_service.login(email=data.username, password=data.password)

    refresh_token, session_token = await auth_service.generate_new_refresh_token(
        user=user
    )

    access_token = auth_service.generate_access_token_from_session(
        user=user, session=session_token
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
    data: Annotated[OAuth2Refresh, Depends()], auth_service: AuthServiceDep
):
    """
    Refresh access token using refresh token.
    - **grant_type**: Must be "refresh_token" for this endpoint
    - **refresh_token**: Refresh token obtained during login
    - **client_id**: The client ID
    - **client_secret**: The client secret
    """

    session_token = await auth_service.get_session_by_refresh_token(
        refresh_token=data.refresh_token
    )

    new_refresh_token, session_token = await auth_service.regenerate_refresh_token(
        session=session_token
    )

    new_access_token = auth_service.generate_access_token_from_session(
        user=session_token.user, session=session_token
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
    data: Annotated[OAuth2Logout, Depends()],
    auth_service: AuthServiceDep,
):
    """
    Logout and revoke refresh token.
    - **refresh_token**: Refresh token obtained during login
    - **client_id**: The client ID
    - **client_secret**: The client secret
    """

    session_token = await auth_service.get_session_by_refresh_token(
        refresh_token=data.refresh_token
    )

    await auth_service.revoke_session(session=session_token)

    return {
        "message": "Logout successful",
    }


@router.post(
    "/logout_all",
    description="Logout from all devices and revoke all refresh tokens",
    status_code=200,
)
async def logout_all(
    data: Annotated[OAuth2Logout, Depends()],
    auth_service: AuthServiceDep,
):
    """
    Logout from all devices and revoke all refresh tokens.
    - **refresh_token**: Refresh token obtained during login
    - **client_id**: The client ID
    - **client_secret**: The client secret
    """

    session_token = await auth_service.get_session_by_refresh_token(
        refresh_token=data.refresh_token
    )

    await auth_service.revoke_all_sessions_for_user(user=session_token.user)

    return {
        "message": "Logout from all devices successful",
    }


@router.get(
    "/devices",
    description="Get all active devices for the current user",
    response_model=DevicesOut,
    status_code=200,
)
async def get_active_devices(
    current_user: Annotated[User, Depends(get_current_active_user)],
    auth_service: AuthServiceDep,
):
    """
    Get all active devices for the current user.
    """

    active_devices = await auth_service.get_active_sessions_for_user(
        user=current_user
    )

    return {
        "message": "Active devices retrieved successfully",
        "active_devices": active_devices,
    }


@router.post(
    "/forgot_password",
    description="Request password reset",
    status_code=200,
)
async def forgot_password(
    email: str,
    auth_service: AuthServiceDep,
    background_tasks: BackgroundTasks,
    email_service: EmailServiceDep,
):
    """
    Request password reset.
    - **email**: Email address of the user
    """

    user = await auth_service.get_user_by_email(email=email)
    token = await auth_service.generate_password_reset_token(user=user)

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
    auth_service: AuthServiceDep,
):
    """
    Reset password using token.
    - **token**: Token sent to the user's email
    - **new_password**: New password for the user account
    """

    user = await auth_service.get_user_by_password_reset_token(token=token)
    await auth_service.delete_password_reset_token(token=token)
    await auth_service.update_user_password(user=user, new_password=new_password)

    return {
        "message": "Password reset successful",
    }


_MAP_EXCEPTION_TO_HTTP_STATUS = {
    UserExistsException: lambda text: HTTPException(
        status_code=400, detail=text or "User with this email or phone already exists."
    ),
    TokenNotFoundException: lambda text: HTTPException(
        status_code=404, detail=text or "Token not found or expired."
    ),
    InvalidCredentialsException: lambda text: HTTPException(
        status_code=401, detail=text or "Invalid email or password."
    ),
    RefreshTokenNotFoundException: lambda text: HTTPException(
        status_code=404,
        detail=text or "Refresh token not found or expired. Please login again.",
    ),
    UserNotFoundException: lambda text: HTTPException(
        status_code=404, detail=text or "User not found."
    ),
    TokenExpiredException: lambda text: HTTPException(
        status_code=401, detail=text or "Token has expired. Please login again."
    ),
    PasswordResetTokenNotFoundException: lambda text: HTTPException(
        status_code=404, detail=text or "Token not found or expired."
    ),
}

def handle_domain_exception(rep: Request, exception: Exception) -> JSONResponse:
    """
    Handle domain exceptions and map them to appropriate HTTP responses.
    """

    assert isinstance(exception, AuthException)
    
    exception_type = type(exception)
    if exception_type in _MAP_EXCEPTION_TO_HTTP_STATUS:
        http_exception = _MAP_EXCEPTION_TO_HTTP_STATUS[exception_type](str(exception))
        error_code = camel_to_upper_snake_case(exception_type.__name__)
        return create_error_response(
            status_code=http_exception.status_code,
            error_code=error_code,
            message=http_exception.detail,
        )
    else:
        logger.error(
            f"Unhandled AuthException on {rep.method} {rep.url}: {exception}",
            exc_info=True,
        )
        return create_error_response(
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
            message="A system error has occurred, please try again later.",
        )
    