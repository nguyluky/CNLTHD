"""Integration tests for admin permissions, user management, and pagination."""

import pytest
from sqlalchemy import func, select

from app.core.database import User

pytestmark = pytest.mark.anyio


@pytest.fixture
async def admin_client(create_auth_client_for_user, admin_user):
    return await create_auth_client_for_user(admin_user)


@pytest.fixture
def new_user_data():
    return {
        "full_name": "New User",
        "email": "new@example.com",
        "phone": "0909999999",
        "password": "newpassword123",
        "role": "customer",
    }


def assert_public_user(body):
    assert set(body) == {"id", "full_name", "email", "phone", "is_active", "role"}


@pytest.mark.parametrize(
    "method,path",
    [("GET", "/admin/users"), ("POST", "/admin/users"), ("PATCH", "/admin/users/1")],
)
async def test_admin_requires_authentication(client, new_user_data, method, path):
    response = await client.request(method, path, json=new_user_data)
    assert response.status_code == 401


@pytest.mark.parametrize("role", ["customer", "barber"])
@pytest.mark.parametrize("method", ["GET", "POST", "PATCH"])
async def test_admin_rejects_non_admin(
    create_auth_client_for_user,
    customer_user,
    barber_user,
    new_user_data,
    session_factory,
    role,
    method,
):
    user = customer_user if role == "customer" else barber_user
    client = await create_auth_client_for_user(user)
    path = f"/admin/users/{customer_user.id}" if method == "PATCH" else "/admin/users"
    response = await client.request(method, path, json=new_user_data)
    assert response.status_code == 403
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 2
        unchanged = await db.get(User, customer_user.id)
        assert unchanged.email == customer_user.email


@pytest.mark.parametrize("method", ["GET", "POST", "PATCH"])
async def test_admin_rejects_inactive_admin(
    admin_client, admin_user, session_factory, new_user_data, method
):
    async with session_factory() as db:
        user = await db.get(User, admin_user.id)
        user.is_active = False
        await db.commit()
    path = f"/admin/users/{admin_user.id}" if method == "PATCH" else "/admin/users"
    response = await admin_client.request(method, path, json=new_user_data)
    assert response.status_code == 400
    assert response.json()["message"] == "Inactive user"


async def test_list_users(admin_client, admin_user, customer_user, barber_user):
    response = await admin_client.get("/admin/users")
    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["page"], body["size"], body["pages"]) == (3, 1, 10, 1)
    assert {u["id"] for u in body["items"]} == {
        admin_user.id,
        customer_user.id,
        barber_user.id,
    }
    for user in body["items"]:
        assert_public_user(user)


@pytest.mark.parametrize(
    "filters",
    [
        {"full_name": "CUSTOMER"},
        {"email": "customer@"},
        {"phone": "34678"},
        {"role": "customer"},
        {"role": "customer", "email": "customer@", "full_name": "customer"},
    ],
)
async def test_list_users_filters(admin_client, customer_user, barber_user, filters):
    response = await admin_client.get("/admin/users", params=filters)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [u["id"] for u in body["items"]] == [customer_user.id]


async def test_list_users_no_match(admin_client, customer_user):
    response = await admin_client.get(
        "/admin/users", params={"role": "admin", "email": customer_user.email}
    )
    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "size": 10,
        "pages": 0,
    }


async def test_list_users_pagination(admin_client, customer_user, barber_user):
    seen = set()
    for page in (1, 2, 3, 4):
        response = await admin_client.get(
            "/admin/users", params={"page": page, "limit": 1}
        )
        assert response.status_code == 200
        body = response.json()
        assert (body["total"], body["page"], body["size"], body["pages"]) == (
            3,
            page,
            1,
            3,
        )
        ids = {u["id"] for u in body["items"]}
        assert len(body["items"]) == (1 if page <= 3 else 0)
        assert not seen.intersection(ids)
        seen.update(ids)
    assert len(seen) == 3


@pytest.mark.parametrize(
    "params", [{"page": 0}, {"limit": 0}, {"limit": 101}, {"role": "invalid"}]
)
async def test_list_users_invalid_filters(admin_client, params):
    response = await admin_client.get("/admin/users", params=params)
    assert response.status_code == 400
    assert response.json()["error_code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("role", ["customer", "barber", "admin"])
async def test_create_user(
    admin_client, new_user_data, session_factory, email_service, role
):
    payload = {**new_user_data, "role": role}
    response = await admin_client.post("/admin/users", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert_public_user(body)
    for field in ("full_name", "email", "phone", "role"):
        assert body[field] == payload[field]
    async with session_factory() as db:
        user = await db.get(User, body["id"])
        assert user.verify_password(payload["password"])
        assert user.hashed_password != payload["password"]
        assert user.role.value == role
    email_service.send_confirmation_email.assert_not_awaited()


@pytest.mark.parametrize(
    "field,value",
    [
        ("email", "invalid"),
        ("phone", "invalid"),
        ("password", "short"),
        ("full_name", "A"),
        ("role", "invalid"),
    ],
)
async def test_create_user_invalid_data(
    admin_client, new_user_data, session_factory, field, value
):
    response = await admin_client.post(
        "/admin/users", json={**new_user_data, field: value}
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "VALIDATION_ERROR"
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 1


@pytest.mark.parametrize("field", ["full_name", "email", "phone", "password", "role"])
async def test_create_user_missing_field(admin_client, new_user_data, field):
    del new_user_data[field]
    response = await admin_client.post("/admin/users", json=new_user_data)
    assert response.status_code == 400
    assert response.json()["error_code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("field", ["email", "phone"])
async def test_create_user_duplicate(
    admin_client, customer_user, new_user_data, session_factory, field
):
    payload = {**new_user_data, field: getattr(customer_user, field)}
    response = await admin_client.post("/admin/users", json=payload)
    assert response.status_code == 409
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 2


async def test_update_user(admin_client, customer_user, new_user_data, session_factory):
    payload = {**new_user_data, "role": "barber"}
    response = await admin_client.patch(
        f"/admin/users/{customer_user.id}", json=payload
    )
    assert response.status_code == 200
    body = response.json()
    assert_public_user(body)
    assert body["id"] == customer_user.id
    for field in ("full_name", "email", "phone", "role"):
        assert body[field] == payload[field]
    async with session_factory() as db:
        user = await db.get(User, customer_user.id)
        assert user.verify_password(payload["password"])
        assert user.email == payload["email"]
        assert user.phone == payload["phone"]
        assert user.role.value == "barber"


async def test_update_user_partial(
    admin_client, customer_user, customer_data, session_factory
):
    response = await admin_client.patch(
        f"/admin/users/{customer_user.id}", json={"full_name": "Updated Name"}
    )
    assert response.status_code == 200
    async with session_factory() as db:
        user = await db.get(User, customer_user.id)
        assert user.full_name == "Updated Name"
        assert user.email == customer_user.email
        assert user.phone == customer_user.phone
        assert user.role == customer_user.role
        assert user.verify_password(customer_data["password"])


async def test_update_user_same_identifiers(admin_client, customer_user, customer_data):
    response = await admin_client.patch(
        f"/admin/users/{customer_user.id}", json={**customer_data, "role": "customer"}
    )
    assert response.status_code == 200
    assert response.json()["id"] == customer_user.id


async def test_update_user_not_found(admin_client, new_user_data):
    response = await admin_client.patch("/admin/users/99999", json=new_user_data)
    assert response.status_code == 404


@pytest.mark.parametrize("field", ["email", "phone"])
async def test_update_user_duplicate(
    admin_client, customer_user, barber_user, customer_data, session_factory, field
):
    payload = {**customer_data, "role": "customer", field: getattr(barber_user, field)}
    response = await admin_client.patch(
        f"/admin/users/{customer_user.id}", json=payload
    )
    assert response.status_code == 409
    async with session_factory() as db:
        user = await db.get(User, customer_user.id)
        assert user.email == customer_user.email
        assert user.phone == customer_user.phone


@pytest.mark.parametrize(
    "field,value",
    [
        ("email", "invalid"),
        ("phone", "invalid"),
        ("password", "short"),
        ("role", "invalid"),
    ],
)
async def test_update_user_invalid_data(
    admin_client, customer_user, customer_data, session_factory, field, value
):
    payload = {**customer_data, "role": "customer", field: value}
    response = await admin_client.patch(
        f"/admin/users/{customer_user.id}", json=payload
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "VALIDATION_ERROR"
    async with session_factory() as db:
        user = await db.get(User, customer_user.id)
        assert user.email == customer_user.email
        assert user.verify_password(customer_data["password"])
