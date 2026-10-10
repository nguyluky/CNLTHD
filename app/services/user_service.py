from typing import Annotated

from fastapi import Depends
from sqlalchemy import select

from app.core.database import User, get_db
from app.schemas.common import PasswordStr
from app.services.share import ServiceException
from sqlalchemy.ext.asyncio import AsyncSession


class _UserException(ServiceException):
    pass


class InvalidOldPasswordException(_UserException):
    pass


class PhoneExistsException(_UserException):
    pass


class EmailExistsException(_UserException):
    pass


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_current_user_password(
        self, current_user: User, old_password: str, new_password: PasswordStr
    ):
        # verify password
        if not current_user.verify_password(old_password):
            raise InvalidOldPasswordException("Old password is invalid")

        current_user.hash_password(new_password)
        self.db.add(current_user)
        await self.db.commit()

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
                raise PhoneExistsException(
                    "This phone number is currently being used by a different user"
                )

            current_user.phone = update_data["phone"]

        if "email" in update_data:
            email_exists = await self.db.scalar(
                select(User).where(User.email == update_data["email"])
            )

            if email_exists:
                raise EmailExistsException(
                    "This email is currently being used by a different user"
                )

            current_user.email = update_data["email"]

        if "full_name" in update_data:
            current_user.full_name = update_data["full_name"]

        self.db.add(current_user)
        await self.db.commit()
        await self.db.refresh(current_user)

        return current_user


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
