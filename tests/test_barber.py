import pytest

from app.core.database import User, UserRole


pytestmark = pytest.mark.anyio


async def test_get_barbers_returns_barbers_with_pagination_metadata(
    client, barber_user, customer_user
):
    response = await client.get("/barbers")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "items": [
            {
                "id": barber_user.id,
                "full_name": barber_user.full_name,
                "email": barber_user.email,
                "phone": barber_user.phone,
                "is_active": True,
                "role": "barber",
            }
        ],
        "total": 1,
        "page": 1,
        "size": 10,
        "pages": 1,
    }
    assert body["items"][0]["id"] != customer_user.id


@pytest.mark.parametrize(
    "filter_params",
    [
        {"full_name": "Test bar"},
        {"email": "barber@example"},
        {"phone": "090123478"},
        {"is_active": "true"},
    ],
)
async def test_get_barbers_applies_filters(client, barber_user, filter_params):
    response = await client.get("/barbers", params=filter_params)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [barber["id"] for barber in body["items"]] == [barber_user.id]


async def test_get_barbers_paginates_results(client, session_factory, barber_user):
    async with session_factory() as db:
        aaron = User(
            full_name="Aaron Barber",
            email="aaron@example.com",
            phone="0900000001",
            hashed_password="unused",
            role=UserRole.barber,
            is_active=True,
        )
        zoe = User(
            full_name="Zoe Barber",
            email="zoe@example.com",
            phone="0900000003",
            hashed_password="unused",
            role=UserRole.barber,
            is_active=False,
        )
        db.add_all([aaron, zoe])
        await db.commit()

    response = await client.get("/barbers", params={"page": 2, "limit": 2})

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": zoe.id,
                "full_name": zoe.full_name,
                "email": zoe.email,
                "phone": zoe.phone,
                "is_active": zoe.is_active,
                "role": "barber",
            }
        ],
        "total": 3,
        "page": 2,
        "size": 2,
        "pages": 2,
    }


async def test_get_barber_by_id(client, barber_user):
    response = await client.get(f"/barbers/{barber_user.id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": barber_user.id,
        "full_name": barber_user.full_name,
        "email": barber_user.email,
        "phone": barber_user.phone,
        "is_active": True,
        "role": "barber",
    }


@pytest.mark.parametrize("missing_or_non_barber_id", [0, 999])
async def test_get_barber_by_id_not_found(client, missing_or_non_barber_id):
    response = await client.get(f"/barbers/{missing_or_non_barber_id}")

    assert response.status_code == 404
    assert response.json() == {
        "error_code": "NOT_FOUND",
        "message": "Barber not found",
    }


async def test_get_barber_by_id_does_not_return_other_roles(client, customer_user):
    response = await client.get(f"/barbers/{customer_user.id}")

    assert response.status_code == 404
    assert response.json()["message"] == "Barber not found"
