from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


ID = BigInteger().with_variant(Integer(), "sqlite")
TIMESTAMP = DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(255))


class LoginSession(Base):
    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP)


class Note(Base):
    __tablename__ = "notes"
    __table_args__ = (Index("ix_notes_feed", "deleted_at", "published_at", "id"),)

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)
    version: Mapped[int] = mapped_column(ID, default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    # A stable demo key prevents seeding from overwriting edits or reviving a deleted note.
    seed_key: Mapped[str | None] = mapped_column(String(64), unique=True)


class NoteImage(Base):
    __tablename__ = "note_images"
    __table_args__ = (UniqueConstraint("note_id", "position", name="uq_note_image_position"),)

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id"))
    position: Mapped[int] = mapped_column(Integer)
    media_type: Mapped[str] = mapped_column(String(32))
    content: Mapped[bytes] = mapped_column(
        LargeBinary().with_variant(mysql.MEDIUMBLOB(), "mysql"), deferred=True
    )


class Favorite(Base):
    __tablename__ = "favorites"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)


class SearchOutbox(Base):
    __tablename__ = "search_outbox"
    __table_args__ = (
        UniqueConstraint("note_id", "version", name="uq_outbox_note_version"),
        Index("ix_outbox_pending", "status", "next_attempt_at", "id"),
    )

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id"))
    version: Mapped[int] = mapped_column(ID)
    snapshot: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)
    last_error: Mapped[str | None] = mapped_column(Text)
