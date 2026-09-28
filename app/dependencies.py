
from fastapi import Depends, HTTPException, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Annotated
from fastapi import status

from fastapi.security import OAuth2PasswordBearer 

from app.core.database import User, get_db
from app.core.security import decode_access_token
from app.core.config import config
from app.core.email import EmailServiceInterface, EmailService, MockEmailService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
    except Exception as e:
        raise credentials_exception

    if not payload:
        raise credentials_exception
    
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


def get_email_service() -> EmailServiceInterface:
    # return EmailService.get_instance(api_key=config.BIRD_API_KEY)
    return MockEmailService()  # Use the mock service for testing

EmailServiceDep = Annotated[EmailServiceInterface, Depends(get_email_service)]
