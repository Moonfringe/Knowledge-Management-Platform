from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=401,
                            detail="无效或已过期的凭证",
                            headers={"WWW-Authenticate": "Bearer"})
    return user_id
