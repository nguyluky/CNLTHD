from app.core.database import get_db
from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.services.services_service import *
from app.schemas.services import ServiceFilterParamForPublic, ServiceOutForPublic
from typing import Annotated
from app.schemas.common import PageResponse

router = APIRouter(prefix="/services", tags=["Services"])

@router.get(
    "",
    description="Get all services",
    response_model=PageResponse[ServiceOutForPublic],
    status_code=status.HTTP_200_OK,
)
async def get_services_public(
    filter: Annotated[ServiceFilterParamForPublic, Query()],
    services_service: ServicesServiceDep
    ):
    """
    Get all services.
    """
    items, total, pages = await services_service.get_filtered_services_for_public(filter=filter)

    validated_items = [
        ServiceOutForPublic.model_validate(service, from_attributes=True) for service in items
    ]

    return PageResponse[ServiceOutForPublic](
        items=validated_items,
        total=total,
        page=filter.page,
        size=filter.limit,
        pages=pages,
    )

@router.get(
    "/{service_id}",
    description="Get a service by ID",
    response_model=ServiceOutForPublic,
    status_code=status.HTTP_200_OK,
)
async def get_service_by_id_public(
    service_id: int, 
    services_service: ServicesServiceDep
    ):
    """
    Get a service by ID.
    """

    service = await services_service.get_service_by_id_with_active_check(service_id=service_id)
    
    return service

map_exception = {
    ServiceNotFoundException: lambda e: HTTPException(
        status_code=404, detail=e or "Service not found"
    ),
}