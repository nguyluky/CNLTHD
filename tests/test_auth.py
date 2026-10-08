from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from uuid import UUID

import pytest

from sqlalchemy import func, select

from app.core.database import SessionToken, User
from app.core.config import config
from app.core.security import decode_token, hash_sha256
from app.schemas.auth import LoginOut

pytestmark = pytest.mark.anyio


def confirmation_token(email_service):
    link = email_service.send_confirmation_email.call_args.kwargs["confirmation_link"]
    return urlparse(link).path.rsplit("/", 1)[-1]


async def test_register_user(
    client,
    session_factory,
    customer_data,
    cache,
    redis_client,
    email_service,
):
    response = await client.post("/auth/register", json=customer_data)
    assert response.status_code == 201
    assert response.json() == {
        "message": "User registered successfully. Please check your email to confirm your registration."
    }
    token = confirmation_token(email_service)
    assert str(UUID(token)) == token
    email_service.send_confirmation_email.assert_awaited_once_with(
        to=customer_data["email"],
        confirmation_link=f"{config.BASE_URL}/auth/confirm/{token}",
    )
    assert (
        await cache.get(f"register:{token}", eviction_group="register") == customer_data
    )
    keys = await redis_client.keys(f"*register:{token}")
    assert len(keys) == 1
    assert 0 < await redis_client.ttl(keys[0]) <= 3600
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 0


async def test_confirm_registration(
    client, session_factory, customer_data, cache, email_service
):
    """
    nghiệm vụ:
    1. gọi POST /auth/register để tạo token
    2. gọi POST /auth/confirm/{token} để xác nhận đăng ký tạo user trong database
    3. kiểm tra token đã bị xóa khỏi cache và Redis | user đã được tạo trong database
    """

    response = await client.post("/auth/register", json=customer_data)
    assert response.status_code == 201
    token = confirmation_token(email_service)
    response = await client.post(f"/auth/confirm/{token}")
    assert response.status_code == 200
    assert response.json() == {"message": "User registered successfully"}
    assert await cache.get(f"register:{token}", eviction_group="register") is None

    async with session_factory() as db:
        user = await db.scalar(select(User).where(User.email == customer_data["email"]))
        assert user is not None
        assert user.full_name == customer_data["full_name"]
        assert user.phone == customer_data["phone"]
        assert user.hashed_password != customer_data["password"]
        assert user.verify_password(customer_data["password"])

    response = await client.post(f"/auth/confirm/{token}")
    assert response.status_code == 404
    assert response.json()["message"] == "Token not found or expired."
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 1


@pytest.mark.parametrize("duplicate_field", ["email", "phone", "both"])
async def test_register_existing_user(
    client, session_factory, customer_data, duplicate_field, email_service
):
    """
    nghiệm vụ:
    1. đầu tiên là tạo một user mới bằng cách gọi POST /auth/register
    2. xác nhận user bằng cách gọi POST /auth/confirm/{token}
    3. sau đó thử đăng ký một user khác với cùng email hoặc phone hoặc cả hai, và kiểm tra rằng server trả về lỗi 400 theo domain exception handler hiện tại
    4. xác nhận rằng email_service.send_confirmation_email không được gọi và số lượng user trong database vẫn là 1
    """

    response = await client.post("/auth/register", json=customer_data)
    assert response.status_code == 201

    response = await client.post(f"/auth/confirm/{confirmation_token(email_service)}")
    assert response.status_code == 200
    email_service.reset_mock()

    other_user = {
        **customer_data,
        "full_name": "Another User",
        "email": "another@example.com",
        "phone": "0907654321",
    }
    for field in ("email", "phone"):
        if duplicate_field in (field, "both"):
            other_user[field] = customer_data[field]

    response = await client.post("/auth/register", json=other_user)
    assert response.status_code == 400
    assert response.json()["message"] == "User with this email or phone already exists."
    email_service.send_confirmation_email.assert_not_awaited()
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 1

    # A rejected registration must not break subsequent requests.
    response = await client.post(
        "/auth/register",
        json={
            **customer_data,
            "email": "new@example.com",
            "phone": "0909999999",
        },
    )
    assert response.status_code == 201


@pytest.mark.parametrize("missing_field", ["full_name", "email", "password", "phone"])
async def test_register_missing_field(
    client, customer_data, missing_field, email_service, redis_client
):
    del customer_data[missing_field]
    response = await client.post("/auth/register", json=customer_data)
    assert response.status_code == 400
    assert response.json()["error_code"] == "VALIDATION_ERROR"
    email_service.send_confirmation_email.assert_not_awaited()
    assert await redis_client.dbsize() == 0


async def test_confirm_unknown_token(client, session_factory):
    response = await client.post("/auth/confirm/unknown-token")
    assert response.status_code == 404
    assert response.json()["message"] == "Token not found or expired."
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 0


async def test_confirm_expired_token(
    client, customer_data, email_service, redis_client, session_factory
):
    response = await client.post("/auth/register", json=customer_data)
    assert response.status_code == 201
    token = confirmation_token(email_service)
    keys = await redis_client.keys(f"*register:{token}")
    assert len(keys) == 1
    # Expire immediately without a timing-dependent sleep.
    await redis_client.pexpire(keys[0], 0)
    response = await client.post(f"/auth/confirm/{token}")
    assert response.status_code == 404
    assert response.json()["message"] == "Token not found or expired."
    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 0


async def test_login(client, registered_user):
    response = await client.post(
        "/auth/login",
        data={
            "username": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Login successful"
    assert body["email"] == registered_user["email"]
    assert body["token_type"] == "bearer"
    payload = decode_token(body["access_token"])
    assert payload["sub"] == registered_user["email"]
    assert payload["role"] == "customer"
    assert "exp" in payload


@pytest.mark.parametrize(
    "field,value",
    [
        ("username", "unknown@example.com"),
        ("password", "wrong-password"),
    ],
)
async def test_login_invalid_credentials(client, registered_user, field, value):
    credentials = {
        "username": registered_user["email"],
        "password": registered_user["password"],
    }
    credentials[field] = value
    response = await client.post("/auth/login", data=credentials)
    assert response.status_code == 401
    assert response.json()["message"] == "Invalid email or password."
    assert "access_token" not in response.json()


async def test_login_unconfirmed_user(client, customer_data):
    response = await client.post("/auth/register", json=customer_data)
    assert response.status_code == 201
    response = await client.post(
        "/auth/login",
        data={
            "username": customer_data["email"],
            "password": customer_data["password"],
        },
    )
    assert response.status_code == 401
    assert response.json()["message"] == "Invalid email or password."


@pytest.fixture
async def login_user(client):
    async def login(user_data) -> LoginOut:
        response = await client.post(
            "/auth/login",
            data={"username": user_data["email"], "password": user_data["password"]},
        )
        assert response.status_code == 200, response.text
        return response.json()

    return login


async def test_login_persists_session(login_user, registered_user, session_factory):
    tokens = await login_user(registered_user)
    assert str(UUID(tokens["refresh_token"])) == tokens["refresh_token"]
    async with session_factory() as db:
        session = await db.scalar(select(SessionToken))
        assert session is not None
        assert session.refresh_token_hash == hash_sha256(tokens["refresh_token"])
        assert session.refresh_token_hash != tokens["refresh_token"]
        assert session.revoked_at is None
        assert decode_token(tokens["access_token"])["sid"] == f"session_{session.id}"


async def test_refresh_rotates_token(
    client, login_user, registered_user, session_factory
):
    original = await login_user(registered_user)
    response = await client.post(
        "/auth/refresh", data={"refresh_token": original["refresh_token"]}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email"] == registered_user["email"]
    assert body["token_type"] == "bearer"
    # Token mới phải khác token cũ
    assert body["refresh_token"] != original["refresh_token"]
    assert body["access_token"] != original["access_token"]

    # kiểm tra xem sid của access_token mới phải trùng với sid của access_token cũ
    payload = decode_token(body["access_token"])
    assert payload["sub"] == registered_user["email"]
    assert payload["sid"] == decode_token(original["access_token"])["sid"]

    async with session_factory() as db:
        assert await db.scalar(select(func.count()).select_from(SessionToken)) == 1
        session = await db.scalar(select(SessionToken))
        assert session.refresh_token_hash == hash_sha256(body["refresh_token"])

    # refresh khi đã dùng xẽ bị xóa
    response = await client.post(
        "/auth/refresh", data={"refresh_token": original["refresh_token"]}
    )
    assert response.status_code == 404

    # refresh mới thì ok 
    response = await client.post(
        "/auth/refresh", data={"refresh_token": body["refresh_token"]}
    )
    assert response.status_code == 200


@pytest.mark.parametrize("endpoint", ["refresh", "logout", "logout_all"])
@pytest.mark.parametrize("token", ["unknown-token", ""])
async def test_session_endpoint_invalid_token(client, endpoint, token):
    response = await client.post(f"/auth/{endpoint}", data={"refresh_token": token})
    assert response.status_code == 404
    assert response.json() == {
        "error_code": "REFRESH_TOKEN_NOT_FOUND_EXCEPTION",
        "message": "Refresh token not found or expired. Please login again.",
    }


@pytest.mark.parametrize("endpoint", ["refresh", "logout", "logout_all"])
async def test_session_endpoint_revoked_token(
    client, login_user, registered_user, endpoint
):
    tokens = await login_user(registered_user)
    data = {"refresh_token": tokens["refresh_token"]}
    response = await client.post("/auth/logout", data=data)
    assert response.status_code == 200
    response = await client.post(f"/auth/{endpoint}", data=data)
    assert response.status_code == 404
    assert (
        response.json()["message"]
        == "Refresh token has been revoked. Please login again."
    )


async def test_refresh_expired_token(
    client, login_user, registered_user, session_factory
):
    tokens = await login_user(registered_user)

    # làm cho token hết hạn
    async with session_factory() as db:
        session = await db.scalar(select(SessionToken))
        session.expired_at = datetime.now(timezone.utc) - timedelta(days=1)
        await db.commit()
    
    response = await client.post(
        "/auth/refresh", data={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 401
    assert response.json() == {
        "error_code": "TOKEN_EXPIRED_EXCEPTION",
        "message": "Refresh token has expired. Please login again.",
    }
    async with session_factory() as db:
        session = await db.scalar(select(SessionToken))
        assert session.refresh_token_hash == hash_sha256(tokens["refresh_token"])


async def test_logout_only_revokes_current_session(
    client, login_user, registered_user, session_factory
):
    first = await login_user(registered_user)
    second = await login_user(registered_user)

    hash_first = hash_sha256(first["refresh_token"])
    hash_second = hash_sha256(second["refresh_token"])

    response = await client.post(
        "/auth/logout", data={"refresh_token": first["refresh_token"]}
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Logout successful"}
    async with session_factory() as db:
        sessions = {
            s.refresh_token_hash: s for s in (await db.scalars(select(SessionToken))).all()
        }
        assert sessions[hash_first].revoked_at is not None
        assert sessions[hash_second].revoked_at is None


async def test_logout_all_preserves_other_users_sessions(
    client, login_user, registered_user, register_user, barber_data, session_factory
):
    first = await login_user(registered_user)
    second = await login_user(registered_user)
    other_user = await register_user(barber_data)
    other = await login_user(other_user)
    response = await client.post(
        "/auth/logout_all", data={"refresh_token": first["refresh_token"]}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"message": "Logout from all devices successful"}
    async with session_factory() as db:
        sessions = {
            s.refresh_token_hash: s for s in (await db.scalars(select(SessionToken))).all()
        }
        assert sessions[hash_sha256(first["refresh_token"])].revoked_at is not None
        assert sessions[hash_sha256(second["refresh_token"])].revoked_at is not None
        assert sessions[hash_sha256(other["refresh_token"])].revoked_at is None


async def test_devices_requires_authentication(client):
    response = await client.get("/auth/devices")
    assert response.status_code == 401


async def test_devices_lists_only_current_users_active_sessions(
    client, login_user, registered_user, register_user, barber_data
):
    current = await login_user(registered_user)
    revoked = await login_user(registered_user)

    other_user = await register_user(barber_data)
    other = await login_user(other_user)

    response = await client.post(
        "/auth/logout", data={"refresh_token": revoked["refresh_token"]}
    )
    assert response.status_code == 200
    response = await client.get(
        "/auth/devices", headers={"Authorization": f"Bearer {current['access_token']}"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    devices = body["active_devices"]


    sid = decode_token(current["access_token"])["sid"]

    assert isinstance(devices, list)
    # assert [device["id"] for device in devices] == ["current"]
    assert [f"session_{device["id"]}" for device in devices] == [sid]
    assert devices[0]["revoked_at"] is None
    assert "refresh_token_hash" not in devices[0]


async def test_forgot_password(
    client, registered_user, email_service, cache, redis_client, session_factory
):
    response = await client.post(
        "/auth/forgot_password", params={"email": registered_user["email"]}
    )
    assert response.status_code == 200

    link = email_service.send_reset_password_email.call_args.kwargs["reset_link"]
    token = urlparse(link).path.rsplit("/", 1)[-1]
    assert str(UUID(token)) == token
    email_service.send_reset_password_email.assert_awaited_once_with(
        to=registered_user["email"],
        reset_link=f"{config.BASE_URL}/auth/reset_password/{token}",
    )

    async with session_factory() as db:
        user = await db.scalar(
            select(User).where(User.email == registered_user["email"])
        )
        assert await cache.get(
            f"forgot_password:{token}", eviction_group="forgot_password"
        ) == {"user_id": user.id}
    keys = await redis_client.keys(f"*forgot_password:{token}")
    assert len(keys) == 1
    assert 0 < await redis_client.ttl(keys[0]) <= 3600


async def test_forgot_password_unknown_user(client, email_service, redis_client):
    response = await client.post(
        "/auth/forgot_password", params={"email": "unknown@example.com"}
    )
    assert response.status_code == 404
    assert response.json()["message"] == "User not found."
    email_service.send_reset_password_email.assert_not_awaited()
    assert await redis_client.dbsize() == 0


async def test_reset_password(
    client, registered_user, email_service, cache, session_factory
):
    response = await client.post(
        "/auth/forgot_password", params={"email": registered_user["email"]}
    )
    assert response.status_code == 200
    link = email_service.send_reset_password_email.call_args.kwargs["reset_link"]
    token = urlparse(link).path.rsplit("/", 1)[-1]
    new_password = "new-secure-password"
    response = await client.post(
        f"/auth/reset_password/{token}", params={"new_password": new_password}
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Password reset successful"}
    assert (
        await cache.get(f"forgot_password:{token}", eviction_group="forgot_password")
        is None
    )
    async with session_factory() as db:
        user = await db.scalar(
            select(User).where(User.email == registered_user["email"])
        )
        assert user.verify_password(new_password)
        assert not user.verify_password(registered_user["password"])
    for password, status in [(registered_user["password"], 401), (new_password, 200)]:
        response = await client.post(
            "/auth/login",
            data={"username": registered_user["email"], "password": password},
        )
        assert response.status_code == status
    response = await client.post(
        f"/auth/reset_password/{token}", params={"new_password": "another-password"}
    )
    assert response.status_code == 404


@pytest.mark.parametrize("expired", [False, True])
async def test_reset_password_invalid_token(
    client, customer_user, cache, redis_client, session_factory, customer_data, expired
):
    token = "invalid-reset-token"
    if expired:
        await cache.set(
            f"forgot_password:{token}",
            {"user_id": customer_user.id},
            ttl=3600,
            eviction_group="forgot_password",
        )
        keys = await redis_client.keys(f"*forgot_password:{token}")
        assert len(keys) == 1
        await redis_client.pexpire(keys[0], 0)
    response = await client.post(
        f"/auth/reset_password/{token}", params={"new_password": "new-password"}
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "PASSWORD_RESET_TOKEN_NOT_FOUND_EXCEPTION"
    async with session_factory() as db:
        user = await db.get(User, customer_user.id)
        assert user.verify_password(customer_data["password"])


async def test_reset_password_deleted_user(client, cache):
    await cache.set(
        "forgot_password:deleted-user",
        {"user_id": 99999},
        ttl=3600,
        eviction_group="forgot_password",
    )
    response = await client.post(
        "/auth/reset_password/deleted-user", params={"new_password": "new-password"}
    )
    assert response.status_code == 404
    print(response.json())
    assert response.json()["message"] == "User not found."


@pytest.mark.parametrize(
    "endpoint", ["/auth/forgot_password", "/auth/reset_password/some-token"]
)
async def test_password_endpoint_missing_parameter(client, endpoint, email_service):
    response = await client.post(endpoint)
    assert response.status_code == 400
    assert response.json()["error_code"] == "VALIDATION_ERROR"
    email_service.send_reset_password_email.assert_not_awaited()
