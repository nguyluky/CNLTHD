import pytest
from app.core.database import Service
from app.schemas.services import ServiceFilterParamForPrivate, ServiceOutForPublic
from app.services import services_service
from tests.test_booking import sample_service
from decimal import Decimal


pytestmark = pytest.mark.anyio

@pytest.fixture
async def sample_services(session_factory):
    services = [
        Service(
            name="Cắt tóc nam",
            description="Cắt tóc nam cơ bản",
            price=Decimal("100000"),
            duration_minutes=30,
            is_active=True,
        ),
        Service(
            name="Cắt tóc nữ",
            description="Cắt tóc nữ cơ bản",
            price=Decimal("120000"),
            duration_minutes=45,
            is_active=True,
        ),
        Service(
            name="Cắt tóc trẻ em",
            description=None,
            price=Decimal("80000"),
            duration_minutes=20,
            is_active=False,
        ),
    ]
    async with session_factory() as db:
        db.add_all(services)
        await db.commit()
        for service in services:
            await db.refresh(service)
    return services

# get service by id success
async def test_get_service_by_id(client, sample_services):
    service = sample_services[0]

    response = await client.get(f"/services/{service.id}")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": service.id,
        "name": service.name,
        "description": service.description,
        "price": "100000.00",
        "duration_minutes": service.duration_minutes,
    }

# get service by id not found
@pytest.mark.parametrize(
    ("service_id", "message"),
    [
        (999, "Not Found Service"),
        (3, "Service is inactive"),
    ],
)
async def test_get_service_by_id_not_found(
    client, sample_services, service_id, message
):
    response = await client.get(f"/services/{service_id}")

    assert response.status_code == 404
    assert response.json() == {"error_code": "NOT_FOUND", "message": message}

# get services with filter
async def test_get_services(client, sample_services):
    response = await client.get("/services", params={"name": "nam", "page": 1, "limit": 10})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["size"] == 10
    assert body["pages"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0] == {
        "id": sample_services[0].id,
        "name": sample_services[0].name,
        "description": sample_services[0].description,
        "price": "100000.00",
        "duration_minutes": sample_services[0].duration_minutes,
    }
