from typing import Annotated
from app.schemas.common import PageResponse
from app.dependencies import require_roles
from app.core.database import UserRole, get_db, User
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.schemas.services import ServiceCreateIn, ServiceFilterParamForPrivate, ServiceOutForPrivate, ServiceUpdateIn
from app.services import services_service
from app.core.exception import NotFoundException

router = APIRouter(prefix="/admin/services", tags=["Services"])

@router.get(
    "",
    description="Get all services for admin",
    response_model=PageResponse[ServiceOutForPrivate],
    status_code=status.HTTP_200_OK,
)
async def get_services(
    filter: Annotated[ServiceFilterParamForPrivate, Query()],
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(require_roles(UserRole.admin))
    ):
    """
    Get all services for admin.
    """

    try:
        items, total, pages = await services_service.get_filtered_services_for_private(filter=filter, db=db)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    validated_items = [
        ServiceOutForPrivate.model_validate(service, from_attributes=True) for service in items
    ]

    return PageResponse[ServiceOutForPrivate](
        items=validated_items,
        total=total,
        page=filter.page,
        size=filter.limit,
        pages=pages,
    )

@router.get(
    "{service_id}",
    description="Get a service by ID for admin",
    response_model=ServiceOutForPrivate,
    status_code=status.HTTP_200_OK,
)
async def get_service_by_id(
    service_id: int, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(require_roles(UserRole.admin))
    ):
    """
    Get a service by ID for admin.
    """
    try:
        service = await services_service.get_service_by_id(service_id, db=db)
    except NotFoundException as e:
        raise e
    
    return service

@router.post(
    "",
    description="Create a new service",
    response_model=ServiceOutForPrivate,
    status_code=status.HTTP_201_CREATED,
)
async def create_service(
    body: ServiceCreateIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin))
):
    """
    Create a new service.
    """
    new_data = body.model_dump()
    service = await services_service.create_service(body=new_data, db=db)
    
    return service

@router.patch(
    "/{service_id}",
    description="Update a service",
    response_model=ServiceOutForPrivate,
    status_code=status.HTTP_200_OK,
)
async def update_service(
    service_id: int,
    body: ServiceUpdateIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin))
):
    """
    Update a service.
    """
    new_data = body.model_dump(exclude_unset=True)
    try:
        service = await services_service.update_service(service_id, body=new_data, db=db)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return service