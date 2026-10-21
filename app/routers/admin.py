from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request
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


@router.get(
    "/users", 
    summary="Get all users.", 
    response_model=PageResponse[UserOut]
)
async def get_all_users(
    filter: Annotated[GetAllUsersFilterIn, Query()], admin_service: AdminServiceDep
):

    limit = filter.limit
    offset = (filter.page - 1) * limit

    items, total = await admin_service.get_all_users(
        full_name=filter.full_name,
        email=filter.email,
        phone=filter.phone,
        role=filter.role,
        limit=limit,
        offset=offset
    )

    validated_items = [UserOut.model_validate(user, from_attributes=True) for user in items]

    return create_page_response(
        items=validated_items,
        total=total or 0,
        page=filter.page,
        size=filter.limit,
    )


@router.post(
    "/users", 
    summary="Create a new user.", 
    status_code=201, 
    response_model=UserOut
)
async def create_user(user: CreateUserIn, admin_service: AdminServiceDep):
    """
    Create a new user.
    - **full_name**: new user full name
    - **email**: new user email
    - **phone**: new user phone
    - **role**: new user role
    """
    new_user = await admin_service.create_user(
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        password=user.password,
        role=user.role,
    )
    return new_user


@router.patch(
    "/users/{user_id}", 
    summary="Update a user.", 
    response_model=UserOut
)
async def update_user(
    user_id: int,
    user_update: UserUpdateIn,
    admin_service: AdminServiceDep,
):
    """
    Update a specified user.
    - **full_name**: Optional new full name
    - **email**: Optional new email
    - **phone**: Optional new phone
    - **role**: Optional new role
    """
    user = await admin_service.update_user(
        user_id,
        full_name=user_update.full_name,
        email=user_update.email,
        phone=user_update.phone,
        password=user_update.password,
        role=user_update.role,
    )
    return user


map_exception = {
    UserAlreadyExistsException: lambda e: HTTPException(
        status_code=409, detail=e or "User with this email or phone already exists"
    ),
}
