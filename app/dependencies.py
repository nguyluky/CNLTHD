from typing import Optional
import uuid

from fastapi import Cookie, Depends, HTTPException, HTTPException, Header, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Annotated
from fastapi import status

from fastapi.security import OAuth2PasswordBearer

from app.core.logger import logger
from app.core.database import User, get_db
from app.core.security import decode_token
from app.core.database import User, UserRole, get_db
from app.core.config import config
from user_agents import parse
from app.services.email_service import EmailServiceFactory, EmailServiceInterface, EmailService, MockEmailService


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", refreshUrl="/auth/refresh")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: AsyncSession = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    invid_token_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token type",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
    except Exception as e:
        raise credentials_exception

    if not payload:
        raise credentials_exception

    if payload.get("type") != "access":
        raise invid_token_exception

    user_email = payload.get("sub")
    if user_email is None:
        raise credentials_exception

    user = await db.scalar(select(User).where(User.email == user_email))

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_active_admin(
    req: Request, current_user: User = Depends(get_current_active_user)
):
    if not current_user.is_admin():
        logger.warning(
            f"{current_user.email}({current_user.role.value}) is trying to access admin route {req.url.path}"
        )
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user


def get_email_service() -> EmailServiceInterface:
    # return EmailService.get_instance(api_key=config.BIRD_API_KEY)
    return EmailServiceFactory.create_email_service()

def require_roles(*allows_roles: UserRole):
    async def check_role(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in allows_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are unauthorized to perform this action"
            )
        return current_user
    return check_role


EmailServiceDep = Annotated[EmailServiceInterface, Depends(get_email_service)]

