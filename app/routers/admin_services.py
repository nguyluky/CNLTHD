from typing import Annotated
from app.schemas.common import PageResponse
from app.dependencies import require_roles
from app.core.database import UserRole
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.schemas.services import ServiceCreateIn, ServiceFilterParamForPrivate, ServiceOutForPrivate, ServiceUpdateIn
from app.services.services_service import *
from redis_fastapi import CacheBackendDep

router = APIRouter(prefix="/admin/services", 
                   tags=["Services"],
                   dependencies=[Depends(require_roles(UserRole.admin))],
                   )

@router.get(
    "",
    description="Get all services for admin",
    response_model=PageResponse[ServiceOutForPrivate],
    status_code=status.HTTP_200_OK,
)
async def get_services(
    filter: Annotated[ServiceFilterParamForPrivate, Query()],
    services_service: ServicesServiceDep
    ):
    """
    Get all services for admin.
    """
    items, total, pages = await services_service.get_filtered_services_for_private(filter=filter)

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
    "/{service_id}",
    description="Get a service by ID for admin",
    response_model=ServiceOutForPrivate,
    status_code=status.HTTP_200_OK,
)
async def get_service_by_id(
    service_id: int, 
    services_service: ServicesServiceDep 
    ):
    """
    Get a service by ID for admin.
    """
    service = await services_service.get_service_by_id(service_id)
    
    return service

@router.post(
    "",
    description="Create a new service",
    response_model=ServiceOutForPrivate,
    status_code=status.HTTP_201_CREATED,
)
async def create_service(
    body: ServiceCreateIn,
    redis: CacheBackendDep,
    services_service: ServicesServiceDep
):
    """
    Create a new service.
    """
    new_data = body.model_dump()
    service = await services_service.create_service(body=new_data)

    await redis.delete_group("available_slot")
    
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
    redis: CacheBackendDep,
    services_service: ServicesServiceDep
):
    """
    Update a service.
    """
    new_data = body.model_dump(exclude_unset=True)

    service = await services_service.update_service(service_id, body=new_data)

    await redis.delete_group("available_slot")
    
    return service

map_exception = {
    ServiceNotFoundException: lambda e: HTTPException(
        status_code=404, detail=e or "Service not found"
    ),
}