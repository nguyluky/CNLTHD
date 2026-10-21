from typing import Annotated
from app.routers import service_logger
from app.schemas.common import PageResponse, create_page_response
from app.dependencies import require_roles
from app.core.database import UserRole
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.schemas.services import ServiceCreateIn, ServiceFilterParamForPrivate, ServiceOutForPrivate, ServiceUpdateIn
from app.services.services_service import *

router = APIRouter(
    prefix="/admin/services", 
    tags=["Services"],
    dependencies=[Depends(require_roles(UserRole.admin))],
)

@router.get(
    "",
    summary="Get all services for admin,",
    response_model=PageResponse[ServiceOutForPrivate],
    status_code=status.HTTP_200_OK,
)
async def get_services(
    filter: Annotated[ServiceFilterParamForPrivate, Query()],
    services_service: ServicesServiceDep
    ):
    items, total= await services_service.get_filtered_services_for_private(filter=filter)

    return create_page_response(
        items=items,
        total=total,
        page=filter.page,
        size=filter.limit,
    )

@router.get(
    "/{service_id}",
    summary="Get a service by ID for admin.",
    response_model=ServiceOutForPrivate,
    status_code=status.HTTP_200_OK,
)
async def get_service_by_id(
    service_id: int, 
    services_service: ServicesServiceDep 
    ):
    service = await services_service.get_service_by_id(service_id)
    
    return service

@router.post(
    "",
    summary="Create a new service.",
    response_model=ServiceOutForPrivate,
    status_code=status.HTTP_201_CREATED,
)
async def create_service(
    body: ServiceCreateIn,
    services_service: ServicesServiceDep
):
    """
    Create a new service.
    - **name**: new service name
    - **description**: new service description
    - **price**: new service price
    - **duration_minutes**: new service duration in minutes
    """
    new_data = body.model_dump()
    service = await services_service.create_service(body=new_data)
    
    return service

@router.patch(
    "/{service_id}",
    summary="Update a service.",
    response_model=ServiceOutForPrivate,
    status_code=status.HTTP_200_OK,
)
async def update_service(
    service_id: int,
    body: ServiceUpdateIn,
    services_service: ServicesServiceDep
):
    """
    Update a specified service.
    - **name**: Optional new name
    - **description**: Optional new description
    - **price**: Optional new price
    - **duration_minutes**: Optional new duration in minutes
    - **is_active**: Optional should the service be available or not
    """
    new_data = body.model_dump(exclude_unset=True)

    service = await services_service.update_service(service_id, body=new_data)

    return service

map_exception = {
    ServiceNotFoundException: lambda e: HTTPException(
        status_code=404, detail=e or "Service not found"
    ),
}