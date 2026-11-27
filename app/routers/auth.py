from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserOut, Token
from app.security import hash_password, verify_password, create_access_token
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from fastapi.security import OAuth2PasswordRequestForm


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
    except IntegrityError:  # pragma: no cover — 两个并发注册撞在同一毫秒才会走到
        await db.rollback()
        raise HTTPException(status_code=409, detail="用户名已存在")
    return user


@router.post("/login", response_model=Token)
async def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.username == form_data.username))
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}
