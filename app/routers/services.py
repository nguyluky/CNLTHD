from app.core.database import get_db
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.exception import NotFoundException
from app.schemas.services import ServiceFilterParamForPublic, ServiceOutForPublic
from app.services import services_service
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
    db: AsyncSession = Depends(get_db)
    ):
    """
    Get all services.
    """
    try:
        items, total, pages = await services_service.get_filtered_services_for_public(filter=filter, db=db)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

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
    db: AsyncSession = Depends(get_db)
    ):
    """
    Get a service by ID.
    """
    try:
        service = await services_service.get_service_by_id_with_active_check(service_id=service_id, db=db)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    
    return service