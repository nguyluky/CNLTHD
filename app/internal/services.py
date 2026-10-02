from app.dependencies import get_current_active_user
from app.core.database import get_db, Service, User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.services import ServiceCreate, ServiceResponse, ServiceUpdate

router = APIRouter(prefix="/admin/services", tags=["Services"])

@router.get(
    "",
    description="Get all services for admin",
    response_model=list[ServiceResponse],
    status_code=status.HTTP_200_OK,
)
async def get_services(
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
    ):
    """
    Get all services for admin.
    """
    if not current_user.is_admin():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this resource")
    
    services = (await db.scalars(select(Service))).all()
    if  not services or len(services) <= 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No services found")
    
    return services

@router.get(
    "{service_id}",
    description="Get a service by ID for admin",
    response_model=ServiceResponse,
    status_code=status.HTTP_200_OK,
)
async def get_service_by_id(
    service_id: int, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
    ):
    """
    Get a service by ID for admin.
    """
    if not current_user.is_admin():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this resource")
    
    service = await db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    
    return service

@router.post(
    "",
    description="Create a new service",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_service(
    body: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new service.
    """
    if not current_user.is_admin():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this resource")

    service = Service(**body.model_dump())
    db.add(service)
    await db.commit()
    await db.refresh(service)
    return service

@router.patch(
    "/{service_id}",
    description="Update a service",
    response_model=ServiceResponse,
    status_code=status.HTTP_200_OK,
)
async def update_service(
    service_id: int,
    body: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update a service.
    """
    if not current_user.is_admin():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this resource")

    service = await db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(service, key, value)

    db.add(service)
    await db.commit()
    await db.refresh(service)
    return service