from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, DateTime, ForeignKey, Boolean, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from app.database import Base

if TYPE_CHECKING:
    from app.models.tags import Tag


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(MEDIUMTEXT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )
    is_pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )

    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        secondary="note_tags",
        back_populates="notes",
        lazy="selectin",
        order_by="Tag.name",
    )
