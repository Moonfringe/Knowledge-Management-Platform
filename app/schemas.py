from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Any, Annotated

from datetime import datetime

TagName = Annotated[str, Field(min_length=1, max_length=50)]


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200, description="笔记标题，不可为空")
    content: str = Field(max_length=20000, description="笔记内容")
    tags: list[TagName] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)


class NoteBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    is_pinned: bool
    is_archived: bool
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags", mode="before")
    @classmethod
    def tag_names(cls, v: Any) -> list[str]:
        return [t.name if hasattr(t, "name") else t for t in v]


class NoteListItem(NoteBase):
    """列表用：无 content"""


class NoteDetail(NoteBase):
    """详情用：带 content"""
    content: str


class NotePage(BaseModel):
    """GET /notes 的响应：分页包装"""

    total: int
    items: list[NoteListItem]


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, max_length=20000)
    is_pinned: bool | None = None
    is_archived: bool | None = None
    tags: list[TagName] | None = None


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    note_count: int



class NoteTagsUpdate(BaseModel):
    tags: list[TagName]
