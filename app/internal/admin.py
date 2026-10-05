from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import User, get_db
from app.schemas.common import create_error_response
from app.core.helper import camel_to_upper_snake_case
from app.dependencies import get_current_active_admin
from app.schemas.common import PageResponse, create_page_response
from app.schemas.user import UserOut
from app.schemas.admin import *
from app.services.admin_service import *


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    responses={
        # không phải là admin thì trả về 403
        403: {"description": "Not enough permissions"}
    },
    # default=Depends(get_current_active_admin)
    dependencies=[Depends(get_current_active_admin)],
)


@router.get("/users", description="Get all users", response_model=PageResponse[UserOut])
async def get_all_users(
    filter: Annotated[GetAllUsersFilterIn, Query()], admin_service: AdminServiceDep
):

    limit = filter.limit if filter.limit is not None else 10
    offset = (filter.page - 1) * limit if filter.page is not None else 0

    users, total = await admin_service.get_all_users(
        full_name=filter.full_name,
        email=filter.email,
        phone=filter.phone,
        role=filter.role,
        limit=limit,
        offset=offset
    )

    print(users, total, filter.model_dump())

    return create_page_response(
        items=users,
        total=total or 0,
        page=filter.page,
        size=filter.limit,
    )


@router.post(
    "/users", description="Create a new user", status_code=201, response_model=UserOut
)
async def create_user(user: CreateUserIn, admin_service: AdminServiceDep):
    new_user = await admin_service.create_user(
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        password=user.password,
        role=user.role,
    )
    return new_user


@router.patch("/users/{user_id}", description="Update a user", response_model=UserOut)
async def update_user(
    user_id: int,
    user_update: UserUpdateIn,
    admin_service: AdminServiceDep,
):
    user = await admin_service.update_user(
        user_id,
        full_name=user_update.full_name,
        email=user_update.email,
        phone=user_update.phone,
        password=user_update.password,
        role=user_update.role,
    )
    return user


_MAP_EXCEPTION_TO_HTTP_STATUS = {
    UserAlreadyExistsException: lambda e: HTTPException(
        status_code=409, detail=e or "User with this email or phone already exists"
    ),
    UserNotFoundException: lambda e: HTTPException(
        status_code=404, detail=e or "User not found"
    ),
}


def handle_domain_exception(req: Request, exc: Exception) -> JSONResponse:

    assert isinstance(exc, AdminException), "Exception must be an instance of AdminException"

    exception_type = type(exc)
    if exception_type in _MAP_EXCEPTION_TO_HTTP_STATUS:
        http_exception = _MAP_EXCEPTION_TO_HTTP_STATUS[exception_type](str(exc))
        status_code = camel_to_upper_snake_case(exception_type.__name__)
        return create_error_response(
            status_code=http_exception.status_code,
            error_code=status_code,
            message=http_exception.detail,
        )

    raise exc  # Re-raise the exception if it's not handled
