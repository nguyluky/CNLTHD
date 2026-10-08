from typing import Annotated

from fastapi import Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import User, UserRole, get_db
from app.services.share import ServiceException, UserNotFoundException


class _AdminException(ServiceException):
    pass


class UserAlreadyExistsException(_AdminException):
    pass

class AdminService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_users(
        self,
        *,
        full_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        role: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ):
        query = select(User)

        # Filters
        if full_name is not None:
            query = query.where(User.full_name.ilike(f"%{full_name}%"))

        if email is not None:
            query = query.where(User.email.ilike(f"%{email}%"))

        if phone is not None:
            query = query.where(User.phone.ilike(f"%{phone}%"))

        if role is not None:
            query = query.where(User.role == role)

        # Count BEFORE pagination
        total_users = await self.db.scalar(
            select(func.count()).select_from(query.subquery())
        )

        # Sort
        query = query.order_by(User.created_at.desc())

        # Pagination
        if limit is not None:
            query = query.limit(limit)

        if offset is not None:
            query = query.offset(offset)

        users = await self.db.scalars(query)

        return users.all(), total_users
    
    async def create_user(
        self, *, full_name: str, email: str, phone: str, password: str, role: UserRole
    ):
        # check if email or phone already exists
        existing_user = await self.db.scalar(
            select(User).where(or_(User.email == email, User.phone == phone))
        )
        if existing_user:
            raise UserAlreadyExistsException("Email or phone already registered")

        new_user = User()
        new_user.full_name = full_name
        new_user.email = email
        new_user.phone = phone
        new_user.role = role
        new_user.hash_password(password)
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)
        return new_user
    
    async def update_user(
        self, user_id: int, *, full_name: str | None = None, email: str | None = None, phone: str | None = None, password: str | None = None, role: UserRole | None = None
    ):
        user = await self.db.scalar(select(User).where(User.id == user_id))
        if not user:
            raise UserNotFoundException("User not found")

        # check if email or phone already exists for other users
        existing_user = await self.db.scalar(
            select(User).where(
                ((User.email == email) | (User.phone == phone)) & (User.id != user_id)
            )
        )
        if existing_user:
            raise UserAlreadyExistsException("Email or phone already registered")

        if full_name is not None:
            user.full_name = full_name
        if email is not None:
            user.email = email
        if phone is not None:
            user.phone = phone
        if role is not None:
            user.role = role
        if password is not None:
            user.hash_password(password)

        await self.db.commit()
        await self.db.refresh(user)
        return user


def get_admin_service(db: AsyncSession = Depends(get_db)) -> AdminService:
    return AdminService(db)


AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]
