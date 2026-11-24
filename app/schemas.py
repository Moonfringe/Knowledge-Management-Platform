from pydantic import BaseModel, Field, ConfigDict, field_validator, AfterValidator
from typing import Any, Annotated, Literal

from datetime import datetime

TagName = Annotated[str, Field(min_length=1, max_length=50)]


def _bcrypt_byte_limit(v: str) -> str:
    """bcrypt 只接受 72 字节以内，中文一个字 3 字节"""
    if len(v.encode("utf-8")) > 72:
        raise ValueError("密码过长（UTF-8 编码后不得超过 72 字节）")
    return v


Password = Annotated[str, Field(min_length=8, max_length=72), AfterValidator(_bcrypt_byte_limit)]


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


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: Password


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
