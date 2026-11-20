from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user_id
from app.database import get_db
from app.schemas import NoteDetail, NoteCreate, NotePage, NoteUpdate, NoteTagsUpdate
from app.models import Note, Tag
from app.services import get_or_create_tags
from sqlalchemy import func, or_, select

from datetime import datetime

router = APIRouter(
    prefix="/notes",
    tags=["notes"],
)


@router.post("", response_model=NoteDetail, status_code=201)
async def create_note(
        payload: NoteCreate,
        user_id: int = Depends(get_current_user_id),
        db: AsyncSession = Depends(get_db),
):
    tags = await get_or_create_tags(db, user_id, payload.tags)
    note = Note(
        user_id=user_id,
        title=payload.title,
        content=payload.content,
        created_at=payload.created_at,
    )
    note.tags = tags
    db.add(note)
    await db.commit()
    return note


@router.get("/{note_id}", response_model=NoteDetail)
async def get_note(
        note_id: int,
        user_id: int = Depends(get_current_user_id),
        db: AsyncSession = Depends(get_db),
):
    note = await db.get(Note, note_id)
    if note is None or note.user_id != user_id:
        raise HTTPException(status_code=404, detail="笔记不存在")
    return note


@router.get("", response_model=NotePage)
async def get_notes(
        user_id: int = Depends(get_current_user_id),
        keyword: str | None = None,
        tag: str | None = None,
        page: int = Query(1, ge=1),
        size: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
):
    conditions = [Note.user_id == user_id, Note.is_archived.is_(False)]
    if keyword:
        conditions.append(
            or_(
                Note.title.contains(keyword, autoescape=True),
                Note.content.contains(keyword, autoescape=True),
            )
        )
    if tag:
        conditions.append(Note.tags.any(Tag.name == tag))
    total = await db.scalar(select(func.count()).select_from(Note).where(*conditions))
    items = await db.scalars(
        select(Note).where(*conditions)
        .order_by(Note.is_pinned.desc(), Note.updated_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return NotePage(total=total, items=items.all())


@router.patch("/{note_id}", response_model=NoteDetail)
async def update_note(
        payload: NoteUpdate,
        note_id: int,
        user_id: int = Depends(get_current_user_id),
        db: AsyncSession = Depends(get_db),
):
    update_data = payload.model_dump(exclude_unset=True, exclude_none=True)
    tag_names = update_data.pop("tags", None)
    note = await db.get(Note, note_id)
    if note is None or note.user_id != user_id:
        raise HTTPException(status_code=404, detail="笔记不存在")
    for k, v in update_data.items():
        setattr(note, k, v)
    if tag_names is not None:
        note.tags = await get_or_create_tags(db, user_id, tag_names)
        note.updated_at = datetime.now()
    await db.commit()
    return note


@router.put("/{note_id}/tags", response_model=NoteDetail)
async def update_tags(
        payload: NoteTagsUpdate,
        note_id: int,
        user_id: int = Depends(get_current_user_id),
        db: AsyncSession = Depends(get_db),
):
    note = await db.get(Note, note_id)
    if note is None or note.user_id != user_id:
        raise HTTPException(status_code=404, detail="笔记不存在")
    note.tags = await get_or_create_tags(db, user_id, payload.tags)
    note.updated_at = datetime.now()
    await db.commit()
    return note


@router.delete("/{note_id}", status_code=204)
async def delete_note(
        note_id: int,
        user_id: int = Depends(get_current_user_id),
        db: AsyncSession = Depends(get_db),
):
    note = await db.get(Note, note_id)
    if note is None or note.user_id != user_id:
        raise HTTPException(status_code=404, detail="笔记不存在")
    await db.delete(note)
    await db.commit()
    return None
