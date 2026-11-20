from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    # 连接回收时间（默认是-1，代表永不回收）
    pool_recycle=3600,
    # 连接前是否预检查（默认为False）
    pool_pre_ping=True,
)

AsyncSessionFactory = async_sessionmaker(
    # Engine或者其子类对象（这里是AsyncEngine）
    bind=engine,
    # 是否在执行commit操作后Session就过期（默认是True）
    expire_on_commit=False
)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        # ix: index，索引。
        "ix": 'ix_%(column_0_label)s',
        # un: unique，唯—约束
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        # ck: Check，检查约束
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        # fk:Foreign Key,外键约束
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        # pk: Primary Key，主键约束
        "pk": "pk_%(table_name)s"
    })


async def get_db():
    async with AsyncSessionFactory() as session:
        yield session
