import json
import pytest
from sqlalchemy import select
from app.core.database import User


pytestmark = pytest.mark.anyio


async def test_get_user_profile(
    create_auth_client_for_user,
    customer_userA,
):
    auth_client = await create_auth_client_for_user(customer_userA)
    response = await auth_client.get("/users/me")

    # response data must match and the user must be active
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == customer_userA.email
    assert data["phone"] == customer_userA.phone
    assert data["full_name"] == customer_userA.full_name
    assert data["is_active"] == True


async def test_update_profile_success(create_auth_client_for_user, customer_userA):
    new_profile = {
        "full_name": "New Test User",
    }

    auth_client = await create_auth_client_for_user(customer_userA)
    response = await auth_client.patch("/users/me", json=new_profile)

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] != customer_userA.full_name


async def test_update_profile_fail(
    create_auth_client_for_user, customer_userA, session_factory, register_user
):
    another_user = {
        "full_name": "Another User",
        "email": "another@example.com",
        "password": "anotherpassword",
        "phone": "0907654321",
    }

    # register a different user
    await register_user(another_user)

    conflict_payload = {"email": another_user["email"]}

    auth_client = await create_auth_client_for_user(customer_userA)
    response = await auth_client.patch("/users/me", json=conflict_payload)

    assert response.status_code == 409
    assert (
        response.json()["message"]
        == "This email is currently being used by a different user"
    )

    # making sure the user's profile stays the same
    async with session_factory() as db:
        user_in_db = await db.scalar(
            select(User).where(User.email == customer_userA.email)
        )
        assert user_in_db is not None


async def test_update_user_password_success(
    create_auth_client_for_user, customer_userA, customer_dataA
):
    request = {
        "old_password": customer_dataA["password"],
        "new_password": "newtestpassword",
    }

    auth_client = await create_auth_client_for_user(customer_userA)
    response = await auth_client.put("/users/me/password", json=request)
    assert response.status_code == 204


async def test_update_user_password_fail(
    create_auth_client_for_user, customer_userA, customer_dataA
):
    # oldpassword is incorrect
    invalid_oldpass_request = {
        "old_password": "wrongpassword",
        "new_password": "newtestpassword",
    }

    auth_client = await create_auth_client_for_user(customer_userA)
    response = await auth_client.put("/users/me/password", json=invalid_oldpass_request)
    assert response.status_code == 400
    assert response.json()["message"] == "Old password is invalid"

    # oldpassword is incorrect
    invalid_newpass_request = {
        "old_password": customer_dataA["password"],
        "new_password": customer_dataA["password"],
    }

    response = await auth_client.put("/users/me/password", json=invalid_newpass_request)
    assert response.status_code == 400
    assert response.json()["error_code"] == "VALIDATION_ERROR"
