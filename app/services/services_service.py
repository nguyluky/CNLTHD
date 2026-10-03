import math

from app.dependencies import get_current_active_user, require_roles
from app.core.database import UserRole, get_db, Service, User
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exception import NotFoundException
from app.schemas.services import ServiceFilterParamForPrivate, ServiceFilterParamForPublic, ServiceOutForPrivate, ServiceUpdateIn

async def get_filtered_services_for_public(
    filter: ServiceFilterParamForPublic,
    db: AsyncSession
):
    query = select(Service).where(Service.is_active == True)

    if filter.name:
        query = query.where(Service.name.contains(filter.name))

    if filter.min_price is not None:
        query = query.where(Service.price >= filter.min_price)

    if filter.max_price is not None:
        query = query.where(Service.price <= filter.max_price)

    if filter.min_duration_minutes is not None:
        query = query.where(Service.duration_minutes >= filter.min_duration_minutes)

    if filter.max_duration_minutes is not None:
        query = query.where(Service.duration_minutes <= filter.max_duration_minutes)

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    if total == 0:
        raise NotFoundException("Service not found")

    # pagination
    offset = (filter.page - 1) * filter.limit
    paginated_query = (
        query.offset(offset).limit(filter.limit).order_by(Service.name.desc())
    )

    result = await db.scalars(paginated_query)
    items = result.all()
    pages = math.ceil(total / filter.limit)

    return items, total, pages

async def get_filtered_services_for_private(
    filter: ServiceFilterParamForPrivate,
    db: AsyncSession
):
    query = select(Service)

    if filter.name:
        query = query.where(Service.name.contains(filter.name))

    if filter.min_price is not None:
        query = query.where(Service.price >= filter.min_price)

    if filter.max_price is not None:
        query = query.where(Service.price <= filter.max_price)

    if filter.min_duration_minutes is not None:
        query = query.where(Service.duration_minutes >= filter.min_duration_minutes)

    if filter.max_duration_minutes is not None:
        query = query.where(Service.duration_minutes <= filter.max_duration_minutes)

    if filter.is_active is not None:
        query = query.where(Service.is_active == filter.is_active)

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    if total == 0:
        raise NotFoundException("Service not found")

    # pagination
    offset = (filter.page - 1) * filter.limit
    paginated_query = (
        query.offset(offset).limit(filter.limit).order_by(Service.name.desc())
    )

    result = await db.scalars(paginated_query)
    items = result.all()
    pages = math.ceil(total / filter.limit)

    return items, total, pages

async def get_service_by_id(
    service_id: int,
    db: AsyncSession
):
    service = await db.get(Service, service_id)
    if not service:
        raise NotFoundException("Not Found Service")

    return service

async def create_service(
    body: dict,
    db: AsyncSession
) -> Service:
    
    service = Service(**body)
    db.add(service)
    await db.commit()
    await db.refresh(service)

    return service

async def update_service(
    service_id: int,
    body: dict,
    db: AsyncSession
):
    try:
        service = await get_service_by_id(service_id, db=db)
    except NotFoundException as e:
        raise e

    for key, value in body.items():
        setattr(service, key, value)

    db.add(service)
    await db.commit()
    await db.refresh(service)

    return service

async def get_service_by_id_with_active_check(
    service_id: int,
    db: AsyncSession
):
    service = await get_service_by_id(service_id, db=db)

    if not service.is_active:
        raise NotFoundException("Service is inactive")

    return service