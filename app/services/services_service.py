import math
from typing import Annotated

from fastapi import Depends

from app.core.database import Service, get_db
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exception import NotFoundException
from app.schemas.services import ServiceFilterParamForPrivate, ServiceFilterParamForPublic
from app.services.share import ServiceException

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
import math


class _ServiveException(ServiceException):
    pass

class ServiceNotFoundException(_ServiveException):
    pass

class ServicesSevice:
    def __init__(self, db: AsyncSession):
            self.db = db

    async def get_filtered_services(
        self,
        query: Select,
        filter,
    ):
        if filter.name:
            query = query.where(Service.name.contains(filter.name))

        if filter.min_price is not None:
            query = query.where(Service.price >= filter.min_price)

        if filter.max_price is not None:
            query = query.where(Service.price <= filter.max_price)

        if filter.min_duration_minutes is not None:
            query = query.where(
                Service.duration_minutes >= filter.min_duration_minutes
            )

        if filter.max_duration_minutes is not None:
            query = query.where(
                Service.duration_minutes <= filter.max_duration_minutes
            )

        if hasattr(filter, "is_active") and filter.is_active is not None:
            query = query.where(Service.is_active == filter.is_active)

        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        if total == 0:
            raise ServiceNotFoundException("Service not found")

        # pagination
        offset = (filter.page - 1) * filter.limit

        paginated_query = (
            query
            .order_by(Service.name.desc())
            .offset(offset)
            .limit(filter.limit)
        )

        result = await self.db.scalars(paginated_query)

        items = result.all()
        pages = math.ceil(total / filter.limit)

        return items, total, pages


    async def get_filtered_services_for_public(
        self,
        filter: ServiceFilterParamForPublic,
    ):
        query = select(Service).where(Service.is_active.is_(True))

        return await self.get_filtered_services(
            query=query,
            filter=filter,
        )

    async def get_filtered_services_for_private(
        self,
        filter: ServiceFilterParamForPrivate,
    ):
        query = select(Service)

        if filter.is_active is not None:
            query = query.where(Service.is_active == filter.is_active)

        return await self.get_filtered_services(
            query=query,
            filter=filter,
        )

    async def get_service_by_id(
        self,
        service_id: int,
    ):
        service = await self.db.get(Service, service_id)
        if not service:
            raise ServiceNotFoundException("Not Found Service")

        return service

    async def create_service(
        self,
        body: dict,
    ) -> Service:
        
        service = Service(**body)
        self.db.add(service)
        await self.db.commit()
        await self.db.refresh(service)

        return service

    async def update_service(
        self,
        service_id: int,
        body: dict,
    ):
        try:
            service = await self.get_service_by_id(service_id)
        except ServiceNotFoundException as e:
            raise e

        for key, value in body.items():
            setattr(service, key, value)

        self.db.add(service)
        await self.db.commit()
        await self.db.refresh(service)

        return service

    async def get_service_by_id_with_active_check(
        self,
        service_id: int,
    ):
        service = await self.get_service_by_id(service_id)

        if not service.is_active:
            raise ServiceNotFoundException("Service is inactive")

        return service

def get_services_service(db: AsyncSession = Depends(get_db)) -> ServicesSevice:
    return ServicesSevice(db)


ServicesServiceDep = Annotated[ServicesSevice, Depends(get_services_service)]