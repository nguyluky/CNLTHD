from decimal import Decimal
from datetime import timedelta
import decimal

import pytest

from app.core.database import Service
from app.core.security import create_access_token


pytestmark = pytest.mark.anyio

async def test_get_service_by_id(
    client, create_auth_client_for_user, admin_user, sample_services
):
    client = await create_auth_client_for_user(admin_user)
    service = sample_services[0]

    response = await client.get(f"/admin/services/{service.id}")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": service.id,
        "name": service.name,
        "description": service.description,
        "price": "100000.00",
        "duration_minutes": service.duration_minutes,
        "is_active": service.is_active,
    }

async def test_get_service_by_id_not_found(
    client, create_auth_client_for_user, admin_user
):
    client = await create_auth_client_for_user(admin_user)
    service_id = 999
    response = await client.get(f"/admin/services/{service_id}")

    assert response.status_code == 404
    assert response.json() == {
        "error_code": "SERVICE_NOT_FOUND_EXCEPTION",
        "message": "Not Found Service",
    }

async def test_get_services(
    client, create_auth_client_for_user, admin_user, sample_services
):
    client = await create_auth_client_for_user(admin_user)
    response = await client.get(
        "/admin/services",
        params={"name": "nam", "is_active": True, "page": 1, "limit": 10},
    )

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
        "is_active": sample_services[0].is_active,
    }


async def test_get_services_includes_inactive_services(
    client, create_auth_client_for_user, admin_user, sample_services
):
    client = await create_auth_client_for_user(admin_user)

    response = await client.get("/admin/services", params={"is_active": False})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == sample_services[2].id
    assert body["items"][0]["is_active"] is False


async def test_get_services_requires_admin(client, create_auth_client_for_user, customer_userA):
    client = await create_auth_client_for_user(customer_userA)

    response = await client.get("/admin/services")

    assert response.status_code == 403
    assert response.json()["message"] == "You are unauthorized to perform this action"

@pytest.mark.anyio
async def test_create_service(
    client,
    admin_user,
    create_auth_client_for_user
):

    client = await create_auth_client_for_user(admin_user)


    response = await client.post(
        "/admin/services",
        json={
            "name": "Cắt tóc nam",
            "description": "Dịch vụ cắt tóc",
            "price": 100000,
            "duration_minutes": 30,
        }
    )

    assert response.status_code == 201, response.text

    body = response.json()
    assert body["name"] == "Cắt tóc nam"
    assert body["description"] == "Dịch vụ cắt tóc"
    assert Decimal(body["price"]) == Decimal("100000")
    assert body["duration_minutes"] == 30

@pytest.mark.anyio
async def test_update_service(
    client,
    admin_user,
    create_auth_client_for_user,
    sample_services
):
    client = await create_auth_client_for_user(admin_user)

    service_id = sample_services[0].id

    response = await client.patch(
        f"/admin/services/{service_id}",
        json={
            "name": "Cắt tóc nam VIP",
            "description": "Dịch vụ cắt tóc cao cấp",
            "price": 150000,
            "duration_minutes": 45,
        }
    )

    assert response.status_code == 200, response.text

    body = response.json()
    assert body["id"] == service_id
    assert body["name"] == "Cắt tóc nam VIP"
    assert body["description"] == "Dịch vụ cắt tóc cao cấp"
    assert Decimal(body["price"]) == Decimal("150000")
    assert body["duration_minutes"] == 45