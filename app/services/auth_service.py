from datetime import timedelta, timezone
from datetime import datetime
from typing import Annotated
import uuid
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from redis_fastapi import CacheBackendDep
from sqlalchemy.orm import selectinload

from app.core.config import configEnv
from app.core.database import SessionToken, User, get_db
from app.core.security import hash_sha256
from app.core.exception import DomainException, UserNotFoundException
from app.routers import service_logger

class _AuthException(DomainException):
    """Base class for authentication-related exceptions."""
    pass

class UserExistsException(_AuthException):
    """Raise this exception if email or phone from a create user request already exists in the database."""

    pass

class TokenNotFoundException(_AuthException):
    """Raise this exception if the token is expired or cannot be found while checking for token."""

    pass

class InvalidCredentialsException(_AuthException):
    """Raise this exception if email or password is invalid from a login request."""

    pass



class RefreshTokenNotFoundException(_AuthException):
    """Raise this exception if the token is expired or cannot be found during token refreshing."""

    pass


class TokenExpiredException(_AuthException):
    """Raise this exception if the token is expired during token authentication."""

    pass

class PasswordResetTokenNotFoundException(_AuthException):
    """Raise this exception if the token is expired or cannot be found during password reset."""

    pass

class AuthService:
    def __init__(self, redis: CacheBackendDep, db: AsyncSession):
        self.redis = redis
        self.db = db

    async def initialize_user_registration(
        self, *, full_name: str, email: str, password: str, phone: str
    ):
        existing_user = await self.db.execute(
            select(User).where(or_(User.email == email, User.phone == phone))
        )

        if existing_user.scalar_one_or_none():
            service_logger.warning(
                "Failed to register new user: Email or phone already exists", 
                extra={"email": email, "phone": phone}
            )
            raise UserExistsException("User with this email or phone already exists.")

        confirmation_token = str(uuid.uuid4())
        redis_key = f"register:{confirmation_token}"

        await self.redis.set(
            redis_key,
            {
                "full_name": full_name,
                "email": email,
                "password": password,
                "phone": phone,
            },
            ttl=3600,
            eviction_group="register",
        )

        return confirmation_token

    async def confirm_user_registration(self, *, token: str):
        redis_key = f"register:{token}"
        user_data = await self.redis.get(redis_key, eviction_group="register")

        if not user_data:
            service_logger.warning(
                "Failed to retrieve confirmation token from redis: Confirmation token not found or expired."
            )
            raise TokenNotFoundException("Token not found or expired.")

        await self.redis.delete(redis_key, eviction_group="register")
        service_logger.debug(
            "Cache invalidated for registration",
            extra={"redis_key": redis_key}
        )

        user = User()
        user.full_name = user_data["full_name"]
        user.email = user_data["email"]
        user.phone = user_data["phone"]
        user.hash_password(user_data["password"])

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        service_logger.info(
            "New user registration confirmed successfully",
            extra={"user_id": user.id}
        )
        return user

    async def login(self, *, email: str, password: str):
        user = await self.db.execute(select(User).where(User.email == email))
        user = user.scalar_one_or_none()

        if not user or not user.verify_password(password):
            service_logger.warning(
                "Failed login attempt: user not found",
                extra={"email": email}
            )
            raise InvalidCredentialsException("Invalid email or password.")

        service_logger.info(
            "User login successfully",
            extra={"user_id": user.id}
        )
        return user

    async def generate_new_refresh_token(self, *, user: User):
        """
            Generate a new refresh token for the user.

            return refresh_token, session
            refresh_token: str
            session: SessionToken
        """
        
        refresh_token_expires_delta = timedelta(days=configEnv.REFRESH_TOKEN_EXPIRE_DAYS)

        refresh_token = str(uuid.uuid4())

        # hash SHA256
        refresh_token_hash = hash_sha256(refresh_token)

        session = SessionToken()

        session.user_id = user.id
        session.refresh_token_hash = refresh_token_hash

        session.expired_at = (
            datetime.now(timezone.utc) + refresh_token_expires_delta
        )

        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        service_logger.info(
            "Refresh token created successfully",
            extra={"user_id": user.id, "session_id": session.id}
        )

        return refresh_token, session

    def generate_access_token_from_session(
        self, *, user: User, session: SessionToken
    ):
        access_token_expires_delta = timedelta(
            minutes=configEnv.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        access_token = user.create_access_token(
            expires_delta=access_token_expires_delta, sid=f"session_{session.id}"
        )

        service_logger.info(
            "Access token from session created successfully",
            extra={"session_id": session.id}
        )
        return access_token

    async def get_session_by_refresh_token(self, *, refresh_token: str):
        refresh_token_hash = hash_sha256(refresh_token)
        session = await self.db.execute(
            select(SessionToken).where(
                SessionToken.refresh_token_hash == refresh_token_hash
            ).options(
                # eager load the user relationship
                selectinload(SessionToken.user)
            )
        )
        session = session.scalar_one_or_none()

        if not session:
            service_logger.warning(
                "Session's refresh token not found or expired"
            )
            raise RefreshTokenNotFoundException(
                "Refresh token not found or expired. Please login again."
            )

        if session.revoked_at is not None:
            service_logger.warning(
                "Session's refresh token has been revoked",
                extra={"session_id": session.id}
            )
            raise RefreshTokenNotFoundException(
                "Refresh token has been revoked. Please login again."
            )
        
        if session.expired_at < datetime.now():
            service_logger.warning(
                "Session's refresh token has expired",
                extra={"session_id": session.id}
            )
            raise TokenExpiredException(
                "Refresh token has expired. Please login again."
            )

        service_logger.info(
            "Successfully retrieve session fron refresh token",
            extra={"session_id": session.id}
        )

        return session

    async def regenerate_refresh_token(self, *, session: SessionToken):
        refresh_token_expires_delta = timedelta(days=configEnv.REFRESH_TOKEN_EXPIRE_DAYS)
        new_refresh_token = str(uuid.uuid4())
        new_refresh_token_hash = hash_sha256(new_refresh_token)

        session.refresh_token_hash = new_refresh_token_hash
        session.expired_at = (
            datetime.now(timezone.utc) + refresh_token_expires_delta
        )

        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        service_logger.info(
            "Refresh token refreshed successfully",
            extra={"session_id": session.id}
        )

        return new_refresh_token, session

    async def revoke_session(self, *, session: SessionToken):
        session.revoked_at = datetime.now(timezone.utc)
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        service_logger.info(
            "Session revoked successfully",
            extra={"session_id": session.id}
        )

        return session

    async def revoke_all_sessions_for_user(self, *, user: User):
        await self.db.execute(
            select(SessionToken).where(SessionToken.user_id == user.id)
        )
        sessions = await self.db.scalars(
            select(SessionToken).where(SessionToken.user_id == user.id)
        )
        for session in sessions:
            session.revoked_at = datetime.now(timezone.utc)
            self.db.add(session)
        await self.db.commit()

        service_logger.info(
            "Sessions from user revoked successfully",
            extra={"user_id": user.id}
        )

    async def get_active_sessions_for_user(self, *, user: User):
        session = await self.db.scalars(
            select(SessionToken)
            .where(SessionToken.user_id == user.id)
            .where(SessionToken.revoked_at.is_(None))
        )
        return session.all()

    async def get_user_by_email(self, *, email: str):
        user = await self.db.scalar(select(User).where(User.email == email))
        if not user:
            service_logger.warning(
                "User lookup by email failed: user not found",
                extra={"email": email}
            )
            raise UserNotFoundException()
        return user

    async def update_user_password(self, *, user: User, new_password: str):
        user.hash_password(new_password)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        service_logger.info(
            "User's password updated successfully",
            extra={"user_id": user.id}
        )
        return user

    async def get_user_by_id(self, *, user_id: int):
        user = await self.db.scalar(select(User).where(User.id == user_id))
        if not user:
            service_logger.warning(
                "User lookup failed: user not found",
                extra={"user_id": user_id}
            )
            raise UserNotFoundException()
        return user
    
    async def generate_password_reset_token(self, *, user: User):
        reset_token = str(uuid.uuid4())
        redis_key = f"forgot_password:{reset_token}"

        await self.redis.set(
            redis_key,
            {"user_id": user.id},
            ttl=3600,
            eviction_group="forgot_password",
        )

        service_logger.info(
            "Reset password token for user created successfully",
            extra={"user_id": user.id}
        )

        return reset_token
    
    async def get_user_by_password_reset_token(self, *, token: str):
        redis_key = f"forgot_password:{token}"
        data = await self.redis.get(redis_key, eviction_group="forgot_password")

        if not data:
            service_logger.warning(
                "Failed to retrieve Password Reset token from redis: Password reset token not found or expired."
            )
            raise PasswordResetTokenNotFoundException("Token not found or expired.")

        user_id = data["user_id"]
        user = await self.get_user_by_id(user_id=user_id)

        return user
    
    async def delete_password_reset_token(self, *, token: str):
        redis_key = f"forgot_password:{token}"
        await self.redis.delete(redis_key, eviction_group="forgot_password")
        service_logger.debug(
            "Cache invalidated for reset password token",
            extra={"redis_key": redis_key}
        )
    

def get_auth_service(
    redis: CacheBackendDep,
    db: AsyncSession = Depends(get_db),
) -> AuthService:
    return AuthService(redis=redis, db=db)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]