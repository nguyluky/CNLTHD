# chứa
# verify_password(hash, password)		Kiểm tra mật khẩu với hash.
# get_password_hash(password)	Băm mật khẩu.
# create_access_token(user)	Tạo và ký JWT.

from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash
import hashlib


from app.core.config import config

hash = PasswordHash.recommended()


def verify_password(plain_password, hashed_password):
    return hash.verify(plain_password, hashed_password)


def get_password_hash(text):
    return hash.hash(text)


def hash_sha256(text: str) -> str:
    """Hash a string using SHA256."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)
    return encoded_jwt


def decode_token(token: str):
    payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
    return payload
