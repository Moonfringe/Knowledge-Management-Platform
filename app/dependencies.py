from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Note
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=401,
                            detail="无效或已过期的凭证",
                            headers={"WWW-Authenticate": "Bearer"})
    return user_id


async def get_owned_note(
        note_id: int,
        user_id: int = Depends(get_current_user_id),
        db: AsyncSession = Depends(get_db)
) -> Note:
    note = await db.get(Note, note_id)
    if note is None or note.user_id != user_id:
        raise HTTPException(status_code=404, detail="笔记不存在")
    return note
