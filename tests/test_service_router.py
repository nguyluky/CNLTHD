import pytest
from app.core.database import Service
from app.schemas.services import ServiceFilterParamForPrivate, ServiceOutForPublic
from app.services import services_service
from decimal import Decimal


pytestmark = pytest.mark.anyio

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
    response = await client.get("/services", params={"page": 1, "limit": 10})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] ==2
    assert body["page"] == 1
    assert body["size"] == 10
    assert body["pages"] == 1
    assert len(body["items"]) == 2


