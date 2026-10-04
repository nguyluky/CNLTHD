from datetime import timedelta, timezone
from datetime import datetime
from typing import Annotated
import uuid
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends, HTTPException
from redis_fastapi import CacheBackendDep
from sqlalchemy.orm import selectinload

from app.core.config import config
from app.core.database import SessionToken, User, get_db
from app.core.security import hash_sha256

class AuthException(Exception):
    """Base class for authentication-related exceptions."""
    pass

class UserExistsException(AuthException):
    """Khi tạo user mới, nếu email hoặc phone đã tồn tại trong database thì raise exception này."""

    pass

class TokenNotFoundException(AuthException):
    """Khi xác nhận token, nếu token không tồn tại hoặc đã hết hạn thì raise exception này."""

    pass


class InvalidCredentialsException(AuthException):
    """Khi đăng nhập, nếu email hoặc password không đúng thì raise exception này."""

    pass



class RefreshTokenNotFoundException(AuthException):
    """Khi refresh token, nếu token không tồn tại hoặc đã hết hạn thì raise exception này."""

    pass


class UserNotFoundException(AuthException):
    """Khi tìm user theo email, nếu user không tồn tại thì raise exception này."""

    pass


class TokenExpiredException(AuthException):
    """Khi xác nhận token, nếu token đã hết hạn thì raise exception này."""

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
            raise TokenNotFoundException("Token not found or expired.")

        await self.redis.delete(redis_key, eviction_group="register")

        user = User()
        user.full_name = user_data["full_name"]
        user.email = user_data["email"]
        user.phone = user_data["phone"]
        user.hash_password(user_data["password"])

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def login(self, *, email: str, password: str):
        user = await self.db.execute(select(User).where(User.email == email))
        user = user.scalar_one_or_none()

        if not user or not user.verify_password(password):
            raise InvalidCredentialsException("Invalid email or password.")

        return user

    async def generate_new_refresh_token(self, *, user: User, device_info: dict):
        refresh_token_expires_delta = timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)

        refresh_token = str(uuid.uuid4())

        # hash SHA256
        refresh_token_hash = hash_sha256(refresh_token)

        session_token = SessionToken()

        session_token.user_id = user.id
        session_token.refresh_token_hash = refresh_token_hash
        session_token.device_id = device_info["device_id"]
        session_token.device_name = device_info["device_name"]
        session_token.device_type = device_info["device_type"]
        session_token.os = device_info["os"]
        session_token.browser = device_info["browser"]
        session_token.ip_address = device_info["ip_address"]
        session_token.user_agent = device_info["user_agent"]

        session_token.expired_at = (
            datetime.now(timezone.utc) + refresh_token_expires_delta
        )

        self.db.add(session_token)
        await self.db.commit()
        await self.db.refresh(session_token)

        return refresh_token, session_token

    def generate_access_token_from_session(
        self, *, user: User, session_token: SessionToken
    ):
        access_token_expires_delta = timedelta(
            minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        access_token = user.create_access_token(
            expires_delta=access_token_expires_delta, sid=f"session_{session_token.id}"
        )
        return access_token

    async def get_session_token_by_refresh_token(self, *, refresh_token: str):
        refresh_token_hash = hash_sha256(refresh_token)
        session_token = await self.db.execute(
            select(SessionToken).where(
                SessionToken.refresh_token_hash == refresh_token_hash
            ).options(
                # eager load the user relationship
                selectinload(SessionToken.user)
            )
        )
        session_token = session_token.scalar_one_or_none()

        if not session_token:
            raise RefreshTokenNotFoundException(
                "Refresh token not found or expired. Please login again."
            )

        if session_token.revoked_at is not None:
            raise RefreshTokenNotFoundException(
                "Refresh token has been revoked. Please login again."
            )
        
        if session_token.expired_at < datetime.now():
            raise TokenExpiredException(
                "Refresh token has expired. Please login again."
            )

        return session_token

    async def regenerate_refresh_token(self, *, session_token: SessionToken):
        refresh_token_expires_delta = timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)
        new_refresh_token = str(uuid.uuid4())
        new_refresh_token_hash = hash_sha256(new_refresh_token)

        session_token.refresh_token_hash = new_refresh_token_hash
        session_token.expired_at = (
            datetime.now(timezone.utc) + refresh_token_expires_delta
        )

        self.db.add(session_token)
        await self.db.commit()
        await self.db.refresh(session_token)

        return new_refresh_token, session_token

    async def revoke_session_token(self, *, session_token: SessionToken):
        session_token.revoked_at = datetime.now(timezone.utc)
        self.db.add(session_token)
        await self.db.commit()
        await self.db.refresh(session_token)

        return session_token

    async def revoke_all_session_tokens_for_user(self, *, user: User):
        await self.db.execute(
            select(SessionToken).where(SessionToken.user_id == user.id)
        )
        session_tokens = await self.db.scalars(
            select(SessionToken).where(SessionToken.user_id == user.id)
        )
        for session_token in session_tokens:
            session_token.revoked_at = datetime.now(timezone.utc)
            self.db.add(session_token)
        await self.db.commit()

    async def get_active_session_tokens_for_user(self, *, user: User):
        session_tokens = await self.db.scalars(
            select(SessionToken)
            .where(SessionToken.user_id == user.id)
            .where(SessionToken.revoked_at.is_(None))
        )
        return session_tokens.all()

    async def get_user_by_email(self, *, email: str):
        user = await self.db.scalar(select(User).where(User.email == email))
        if not user:
            raise UserNotFoundException()
        return user

    async def update_user_password(self, *, user: User, new_password: str):
        user.hash_password(new_password)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def get_user_by_id(self, *, user_id: int):
        user = await self.db.scalar(select(User).where(User.id == user_id))
        if not user:
            raise UserNotFoundException()
        return user


def get_auth_service(
    redis: CacheBackendDep,
    db: AsyncSession = Depends(get_db),
) -> AuthService:
    return AuthService(redis=redis, db=db)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
