from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Response
from PIL import Image, UnidentifiedImageError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, DB, OptionalUser
from app.db import utc_string, utcnow
from app.models import Favorite, Note, NoteImage, SearchOutbox, User


router = APIRouter()
IMAGE_TYPES = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
MAX_IMAGE_BYTES = 4 * 1024**2
Title = Annotated[str, Form(min_length=1, max_length=160)]
Body = Annotated[str, Form(min_length=1, max_length=12000)]


def load_images(files: list[UploadFile]) -> list[tuple[str, bytes]]:
    if not 1 <= len(files) <= 4:
        raise HTTPException(422, "请选择 1 至 4 张图片")
    values = []
    for upload in files:
        raw = upload.file.read(MAX_IMAGE_BYTES + 1)
        if len(raw) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "每张图片最多 4 MiB")
        try:
            with Image.open(BytesIO(raw)) as image:
                kind = IMAGE_TYPES.get(image.format)
                if kind is None or image.width * image.height > 16_000_000:
                    raise HTTPException(422, "请选择不超过 1600 万像素的 PNG、JPEG 或 WebP 图片")
                image.verify()
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
            raise HTTPException(422, "图片内容无效")
        values.append((kind, raw))
    return values


def text_value(value: str) -> str:
    if not value.strip():
        raise HTTPException(422, "标题和正文不能为空")
    return value.strip()


def image_url(note_id: int, image_id: int) -> str:
    return f"/api/notes/{note_id}/images/{image_id}"


def note_images(db: Session, note_id: int, *, lock: bool) -> list[dict]:
    query = select(NoteImage.id).where(NoteImage.note_id == note_id).order_by(NoteImage.position)
    ids = db.scalars(query.with_for_update() if lock else query)
    return [{"id": ident, "url": image_url(note_id, ident)} for ident in ids]


def live_note(db: Session, note_id: int, *, lock: bool = False) -> Note:
    query = select(Note).where(Note.id == note_id, Note.deleted_at.is_(None))
    if lock:
        query = query.with_for_update()
    note = db.scalar(query)
    if note is None:
        raise HTTPException(404, "笔记不存在")
    return note


def owned_note(db: Session, note_id: int, user: User) -> Note:
    note = live_note(db, note_id, lock=True)
    if note.author_id != user.id:
        raise HTTPException(403, "只有作者可以修改这篇笔记")
    return note


def put_images(db: Session, note: Note, values: list[tuple[str, bytes]]) -> None:
    db.execute(delete(NoteImage).where(NoteImage.note_id == note.id))
    for position, (kind, content) in enumerate(values):
        db.add(NoteImage(note_id=note.id, position=position, media_type=kind, content=content))
    db.flush()


def queue_snapshot(db: Session, note: Note, author: User) -> None:
    snapshot = {"note_id": note.id, "version": note.version, "deleted": note.deleted_at is not None}
    if note.deleted_at is None:
        # A locking read sees images committed by a concurrent previous edit under InnoDB.
        cover = db.scalars(
            select(NoteImage.id).where(NoteImage.note_id == note.id, NoteImage.position == 0)
            .with_for_update()
        ).one()
        snapshot.update(
            title=note.title, body=note.body, cover_url=image_url(note.id, cover),
            published_at=utc_string(note.published_at), author_id=author.id, author_name=author.display_name,
        )
    db.add(SearchOutbox(note_id=note.id, version=note.version, snapshot=snapshot))


def create_note_record(
    db: Session, author: User, title: str, body: str,
    images: list[tuple[str, bytes]], seed_key: str | None = None,
) -> Note:
    note = Note(author_id=author.id, title=text_value(title), body=text_value(body), seed_key=seed_key)
    db.add(note)
    db.flush()
    put_images(db, note, images)
    queue_snapshot(db, note, author)
    return note


def detail(db: Session, note: Note, user: User | None, *, lock_images: bool = False) -> dict:
    images = note_images(db, note.id, lock=lock_images)
    return {
        "id": note.id,
        "title": note.title,
        "body": note.body,
        "images": images,
        "cover_url": images[0]["url"],
        "author_id": note.author_id,
        "author_name": db.get(User, note.author_id).display_name,
        "published_at": utc_string(note.published_at),
        "version": note.version,
        "is_favorite": user is not None and db.get(Favorite, (user.id, note.id)) is not None,
    }


def list_cards(db: Session, user: User | None = None) -> dict:
    query = (
        select(Note.id, Note.title, Note.published_at, Note.author_id, User.display_name, NoteImage.id)
        .join(User, User.id == Note.author_id)
        .join(NoteImage, (NoteImage.note_id == Note.id) & (NoteImage.position == 0))
        .where(Note.deleted_at.is_(None))
    )
    if user:
        query = query.join(Favorite, Favorite.note_id == Note.id).where(Favorite.user_id == user.id)
        query = query.order_by(Favorite.created_at.desc(), Note.id.desc())
    else:
        query = query.order_by(Note.published_at.desc(), Note.id.desc())
    return {"items": [
        {"id": ident, "title": title, "published_at": utc_string(published_at),
         "author_id": author_id, "author_name": author_name, "cover_url": image_url(ident, cover)}
        for ident, title, published_at, author_id, author_name, cover in db.execute(query)
    ]}


@router.get("/notes")
def feed(db: DB):
    return list_cards(db)


@router.get("/notes/{note_id}")
def get_note(note_id: int, db: DB, user: OptionalUser):
    return detail(db, live_note(db, note_id), user)


@router.get("/notes/{note_id}/images/{image_id}")
def get_image(note_id: int, image_id: int, db: DB):
    row = db.execute(
        select(NoteImage.media_type, NoteImage.content).join(Note, Note.id == NoteImage.note_id)
        .where(Note.id == note_id, Note.deleted_at.is_(None), NoteImage.id == image_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "图片不存在")
    return Response(row.content, media_type=row.media_type, headers={"Cache-Control": "no-store"})


@router.post("/notes", status_code=201)
def post_note(db: DB, user: CurrentUser, title: Title, body: Body, images: Annotated[list[UploadFile], File()]):
    note = create_note_record(db, user, title, body, load_images(images))
    result = detail(db, note, user)
    db.commit()
    return result


@router.patch("/notes/{note_id}")
def edit_note(
    note_id: int, db: DB, user: CurrentUser,
    title: Annotated[str | None, Form(min_length=1, max_length=160)] = None,
    body: Annotated[str | None, Form(min_length=1, max_length=12000)] = None,
    images: Annotated[list[UploadFile] | None, File()] = None,
):
    # Decode input first, so image validation never holds a note's write lock.
    replacements = load_images(images) if images is not None else None
    note = owned_note(db, note_id, user)
    if title is None and body is None and replacements is None:
        raise HTTPException(422, "请提供要修改的内容")
    if title is not None:
        note.title = text_value(title)
    if body is not None:
        note.body = text_value(body)
    if replacements is not None:
        put_images(db, note, replacements)
    note.version += 1
    queue_snapshot(db, note, user)
    result = detail(db, note, user, lock_images=True)
    db.commit()
    return result


@router.delete("/notes/{note_id}", status_code=204)
def remove_note(note_id: int, db: DB, user: CurrentUser) -> Response:
    note = owned_note(db, note_id, user)
    note.version += 1
    note.deleted_at = utcnow()
    queue_snapshot(db, note, user)
    db.commit()
    return Response(status_code=204)


@router.get("/me/favorites")
def favorites(db: DB, user: CurrentUser):
    return list_cards(db, user)


@router.put("/me/favorites/{note_id}", status_code=204)
def add_favorite(note_id: int, db: DB, user: CurrentUser) -> Response:
    live_note(db, note_id, lock=True)
    existing = db.scalar(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.note_id == note_id).with_for_update()
    )
    if existing is None:
        db.add(Favorite(user_id=user.id, note_id=note_id))
    db.commit()
    return Response(status_code=204)


@router.delete("/me/favorites/{note_id}", status_code=204)
def remove_favorite(note_id: int, db: DB, user: CurrentUser) -> Response:
    db.execute(delete(Favorite).where(Favorite.user_id == user.id, Favorite.note_id == note_id))
    db.commit()
    return Response(status_code=204)
