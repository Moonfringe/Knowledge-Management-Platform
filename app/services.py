from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tag


async def get_or_create_tags(
    db: AsyncSession,
    user_id: int,
    names: list[str],
) -> list[Tag]:
    """按名字取回标签，不存在就新建（不提交事务）。

    返回顺序与入参一致；同一个名字的多种大小写只会产生一个标签。
    """
    # 1. 清洗：去首尾空白、丢空串、按小写去重（保留第一次出现的写法）
    cleaned: dict[str, str] = {}
    for raw in names:
        name = raw.strip()
        if name and name.lower() not in cleaned:
            cleaned[name.lower()] = name

    if not cleaned:
        return []

    # 2. 一次查全已存在的，不要循环 db.get
    found = await db.scalars(
        select(Tag).where(Tag.user_id == user_id, Tag.name.in_(cleaned.values()))
    )
    existing = {t.name.lower(): t for t in found}

    # 3. 缺的才新建，同时按入参顺序拼出结果
    tags: list[Tag] = []
    for lower, original in cleaned.items():
        tag = existing.get(lower)
        if tag is None:
            tag = Tag(user_id=user_id, name=original)
            db.add(tag)
        tags.append(tag)
    return tags

