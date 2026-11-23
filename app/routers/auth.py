from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserOut
from app.security import hash_password
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post("/register", status_code=201, response_model=UserOut)
async def register(
        payload: UserCreate,
        db: AsyncSession = Depends(get_db),
):
    exists = await db.scalar(select(User).where(User.username == payload.username))
    if exists:
        raise HTTPException(status_code=409, detail="用户名已存在")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="用户名已存在")
    return user
