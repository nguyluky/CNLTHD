from typing import Annotated

from fastapi import Depends
from sqlalchemy import select

from app.core.database import User, get_db
from app.routers import service_logger
from app.schemas.common import PasswordStr
from app.core.exception import DomainException
from sqlalchemy.ext.asyncio import AsyncSession


class _UserException(DomainException):
    pass


class InvalidOldPasswordException(_UserException):
    """Raise this exception if old password is invalid in a change password request."""
    pass


class PhoneExistsException(_UserException):
    """Raise this exception if the new phone number matches a phone number in the database."""
    pass


class EmailExistsException(_UserException):
    """Raise this exception if the new email matches an email in the database."""
    pass


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_current_user_password(
        self, current_user: User, old_password: str, new_password: PasswordStr
    ):
        # verify password
        if not await current_user.async_verify_password(old_password):
            service_logger.error(
                "User password update failed: Old password is invalid",
                extra={"user_id": current_user.id}
            )
            raise InvalidOldPasswordException("Old password is invalid")

        await current_user.async_hash_password(new_password)
        self.db.add(current_user)
        await self.db.commit()

        service_logger.info(
            "User password update successfully",
            extra={"user_id": current_user.id}
        )

    async def update_current_user_profile(
        self,
        current_user: User,
        update_data: dict,
    ):
        if not update_data:
            return current_user

        if "phone" in update_data:
            phone_exists = await self.db.scalar(
                select(User).where(User.phone == update_data["phone"])
            )

            if phone_exists:
                service_logger.error(
                    "User profile update failed: Phone number already exists",
                    extra={"user_id": current_user.id, "phone": update_data["phone"]}
                )
                raise PhoneExistsException(
                    "This phone number is currently being used by a different user"
                )

            current_user.phone = update_data["phone"]

        if "email" in update_data:
            email_exists = await self.db.scalar(
                select(User).where(User.email == update_data["email"])
            )

            if email_exists:
                service_logger.error(
                    "User profile update failed: Email already exists",
                    extra={"user_id": current_user.id, "email": update_data["email"]}
                )
                raise EmailExistsException(
                    "This email is currently being used by a different user"
                )

            current_user.email = update_data["email"]

        if "full_name" in update_data:
            current_user.full_name = update_data["full_name"]

        self.db.add(current_user)
        await self.db.commit()
        await self.db.refresh(current_user)

        service_logger.info(
            "User profile update successfully",
            extra={"user_id": current_user.id}
        )

        return current_user


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
