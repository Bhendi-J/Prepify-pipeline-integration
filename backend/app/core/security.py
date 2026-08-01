from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from app.core.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") #shared password hashing context used by authentication helpers
ALGORITHM = "HS256" #JWT signing algorithm used across the backend


def hash_password(password: str) -> str:
    #password hashing helper
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    #password verification helper
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    #JWT creation helper
    if settings.JWT_SECRET_KEY is None:
        raise ValueError("JWT_SECRET_KEY is not configured")

    payload = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=30))
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    #JWT decoding helper
    if settings.JWT_SECRET_KEY is None:
        raise ValueError("JWT_SECRET_KEY is not configured")

    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])