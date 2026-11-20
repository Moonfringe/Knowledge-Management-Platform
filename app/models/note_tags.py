from sqlalchemy import Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NoteTag(Base):
    __tablename__ = "note_tags"
    note_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True, index=True
    )
