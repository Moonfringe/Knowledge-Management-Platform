from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60



def hash_password(plain: str) -> str:
    pwd_bytes = plain.encode("utf8")
    hashed = bcrypt.hashpw(pwd_bytes, bcrypt.gensalt(12)).decode("utf8")
    return hashed


def verify_password(plain: str, hashed: str) -> bool:
    try:
        pwd_bytes = plain.encode("utf8")
        hashed_bytes = hashed.encode("utf8")
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    encode_jwt = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return encode_jwt


def decode_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None
