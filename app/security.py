import bcrypt


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
