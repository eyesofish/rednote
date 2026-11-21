"""Accounts, note images, favorites and versioned search snapshots."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "0001_note_community"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    ident = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    moment = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
    op.create_table(
        "users",
        sa.Column("id", ident, primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("display_name", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", ident, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", moment, nullable=False),
    )
    op.create_table(
        "notes",
        sa.Column("id", ident, primary_key=True),
        sa.Column("author_id", ident, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("published_at", moment, nullable=False),
        sa.Column("version", ident, nullable=False),
        sa.Column("deleted_at", moment),
        sa.Column("seed_key", sa.String(64), unique=True),
    )
    op.create_index("ix_notes_feed", "notes", ["deleted_at", "published_at", "id"])
    op.create_table(
        "note_images",
        sa.Column("id", ident, primary_key=True),
        sa.Column("note_id", ident, sa.ForeignKey("notes.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(32), nullable=False),
        sa.Column("content", sa.LargeBinary().with_variant(mysql.MEDIUMBLOB(), "mysql"), nullable=False),
        sa.UniqueConstraint("note_id", "position", name="uq_note_image_position"),
    )
    op.create_table(
        "favorites",
        sa.Column("user_id", ident, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("note_id", ident, sa.ForeignKey("notes.id"), primary_key=True),
        sa.Column("created_at", moment, nullable=False),
    )
    op.create_table(
        "search_outbox",
        sa.Column("id", ident, primary_key=True),
        sa.Column("note_id", ident, sa.ForeignKey("notes.id"), nullable=False),
        sa.Column("version", ident, nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", moment, nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.UniqueConstraint("note_id", "version", name="uq_outbox_note_version"),
    )
    op.create_index("ix_outbox_pending", "search_outbox", ["status", "next_attempt_at", "id"])


def downgrade():
    for name in ("search_outbox", "favorites", "note_images", "notes", "sessions", "users"):
        op.drop_table(name)
