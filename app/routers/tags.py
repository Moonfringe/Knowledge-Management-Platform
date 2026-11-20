from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.models import Note, NoteTag, Tag
from app.schemas import TagOut

router = APIRouter(
    prefix="/tags",
    tags=["tags"],
)

@router.get("", response_model=list[TagOut])
async def list_tags(
        user_id: int = Depends(get_current_user_id),
        db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Tag.name, func.count(Note.id).label("note_count"))
        .outerjoin(NoteTag, NoteTag.tag_id == Tag.id)
        .outerjoin(Note, and_(
            Note.id == NoteTag.note_id,
            Note.is_archived.is_(False),
            Note.user_id == user_id,
        ))
        .where(Tag.user_id == user_id)
        .group_by(Tag.id)
        .order_by(Tag.name)
    )
    rows = (await db.execute(stmt)).all()
    return [TagOut(name=r.name, note_count=r.note_count) for r in rows]
