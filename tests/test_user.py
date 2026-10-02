import pytest
from sqlalchemy import select

from app.core.database import Base, User, UserRole, get_db
from app.main import app


pytestmark = pytest.mark.anyio


async def test_get_user_profile(auth_client, user_data):
    response = await auth_client.get("/users/me")

    # response data must match and the user must be active
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == user_data["email"]
    assert data["phone"] == user_data["phone"]
    assert data["full_name"] == user_data["full_name"]
    assert data["is_active"] == True


async def test_update_profile_success(auth_client, user_data):
    new_profile = {
        "full_name": "New Test User",
    }

    response = await auth_client.patch("/users/me", json=new_profile)

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] != user_data["full_name"]


async def test_update_profile_fail(
    auth_client, session_factory, user_data, register_user
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

    response = await auth_client.patch("/users/me", json=conflict_payload)

    assert response.status_code == 409
    assert (
        response.json()["message"]
        == "This email is currently being used by a different user"
    )

    # making sure the user's profile stays the same
    async with session_factory() as db:
        user_in_db = await db.scalar(
            select(User).where(User.email == user_data["email"])
        )
        assert user_in_db is not None


async def test_update_user_password_success(auth_client, user_data):
    request = {"old_password": user_data["password"], "new_password": "newtestpassword"}

    response = await auth_client.put("/users/me/password", json=request)
    assert response.status_code == 204


async def test_update_user_password_fail(auth_client, user_data):
    # oldpassword is incorrect
    invalid_oldpass_request = {
        "old_password": "wrongpassword",
        "new_password": "newtestpassword",
    }

    response = await auth_client.put("/users/me/password", json=invalid_oldpass_request)
    assert response.status_code == 400
    assert response.json()["message"] == "Old password is invalid"

    # oldpassword is incorrect
    invalid_newpass_request = {
        "old_password": user_data["password"],
        "new_password": user_data["password"],
    }

    response = await auth_client.put("/users/me/password", json=invalid_newpass_request)
    assert response.status_code == 400
    assert response.json()["error_code"] == "VALIDATION_ERROR"
