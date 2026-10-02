from app.core.database import get_db, Service
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.services import ServiceResponse

router = APIRouter(prefix="/services", tags=["Services"])

@router.get(
    "",
    description="Get all services",
    response_model=list[ServiceResponse],
    status_code=status.HTTP_200_OK,
)
async def get_services(
    db: AsyncSession = Depends(get_db)
    ):
    """
    Get all services.
    """
    services = (await db.scalars(select(Service).where(Service.is_active == True))).all()
    if  not services or len(services) <= 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No services found")
    return services

@router.get(
    "/{service_id}",
    description="Get a service by ID",
    response_model=ServiceResponse,
    status_code=status.HTTP_200_OK,
)
async def get_service_by_id(
    service_id: int, 
    db: AsyncSession = Depends(get_db)
    ):
    """
    Get a service by ID.
    """
    service = await db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    if service.is_active is False:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service is inactive")
    
    return service