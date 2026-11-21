from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import os
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import sessionmaker

from app import campus_import
from app.campus_pack import Pack, PackNote, SearchCase
from app.db import Base, utcnow
from app.models import Note, NoteImage, SearchOutbox, User
from app.search.index import IncompleteSearch
from app.seed import sample_image


@pytest.fixture
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'campus.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    store = sessionmaker(engine, expire_on_commit=False)
    with store.begin() as db:
        for username in ("writer", "other"):
            db.add(User(username=username, display_name=username, password_hash="unused"))
    yield store
    engine.dispose()


@pytest.fixture
def pack():
    notes = [
        PackNote("N001", "租房通勤", "雨天通勤清单", "鞋套放在侧袋。", "images/N001.png",
                 "本人绘制", sample_image("desk"), "image/png"),
        PackNote("N002", "租房通勤", "早八出发前", "雨天通勤把伞放在门边。", "images/N002.png",
                 "本人绘制", sample_image("hill"), "image/png"),
    ]
    return Pack(notes, [SearchCase("雨天通勤", "N001", "N002"), SearchCase("荧光长凳", "", "")], [])


def test_retry_and_extension_preserve_ids_images_and_outbox(factory, pack):
    pilot = replace(pack, notes=pack.notes[:1])
    first = campus_import.import_pack(pilot, "writer", factory)
    full = campus_import.import_pack(pack, "writer", factory)
    repeat = campus_import.import_pack(pack, "writer", factory)
    assert first["ids"]["N001"] == full["ids"]["N001"]
    assert (full["created"], full["reused"]) == (1, 1)
    assert repeat == {"created": 0, "reused": 2, "ids": full["ids"]}
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(NoteImage)) == 2
        assert db.scalar(select(func.count()).select_from(SearchOutbox)) == 2
        for entry in pack.notes:
            event = db.scalar(select(SearchOutbox).where(SearchOutbox.note_id == full["ids"][entry.id]))
            assert event.snapshot["title"] == entry.title
            assert event.snapshot["version"] == 1


def test_conflict_rolls_back_other_notes_and_retains_deletion(factory, pack):
    existing = replace(pack, notes=[pack.notes[1]])
    persisted = campus_import.import_pack(existing, "writer", factory)["ids"]["N002"]
    with pytest.raises(ValueError, match="其他作者"):
        campus_import.import_pack(pack, "other", factory)
    for field, value, message in (("title", "改过的标题", "标题或正文"),
                                  ("image_bytes", pack.notes[0].image_bytes, "配图")):
        changed = replace(pack, notes=[pack.notes[0], replace(pack.notes[1], **{field: value})])
        with pytest.raises(ValueError, match=message):
            campus_import.import_pack(changed, "writer", factory)
    with factory.begin() as db:
        note = db.get(Note, persisted)
        note.deleted_at = utcnow()
    with pytest.raises(ValueError, match="已被删除"):
        campus_import.import_pack(pack, "writer", factory)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Note)) == 1
        assert db.scalar(select(func.count()).select_from(SearchOutbox)) == 1
        assert db.get(Note, persisted).deleted_at is not None


def test_verify_primary_and_order_and_search_availability(factory, pack, monkeypatch):
    client = Mock()
    with pytest.raises(ValueError, match="尚未导入"):
        campus_import.verify_pack(pack, factory=factory, client=client)
    ids = list(campus_import.import_pack(pack, "writer", factory)["ids"].values())
    lookup = Mock(side_effect=lambda _, query: [{"id": n} for n in ids] if query == "雨天通勤" else [])
    monkeypatch.setattr("app.search.index.search_notes", lookup)
    result = campus_import.verify_pack(pack, factory=factory, client=client)
    assert result["search_cases"] == {"雨天通勤": ids, "荧光长凳": []}
    lookup.side_effect = lambda _, query: [{"id": n} for n in reversed(ids)] if query == "雨天通勤" else []
    with pytest.raises(ValueError, match="实际为"):
        campus_import.verify_pack(pack, factory=factory, client=client, timeout=0.05)
    lookup.side_effect = IncompleteSearch()
    with pytest.raises(ValueError, match="搜索服务"):
        campus_import.verify_pack(pack, factory=factory, client=client, timeout=0.05)


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL", "").startswith("mysql"),
                    reason="Set TEST_DATABASE_URL to an isolated MySQL test database")
def test_concurrent_reimport_uses_same_ids_and_single_snapshot(pack, monkeypatch):
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    store = sessionmaker(engine)
    salt = uuid4().hex[:10]
    prefix = f"campus-test-{salt}:"
    username = f"campus-{salt}"
    monkeypatch.setattr(campus_import, "PREFIX", prefix)
    keys = [prefix + row.id for row in pack.notes]
    try:
        # The isolated acceptance database may be entirely new on a first invocation.
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        with engine.begin() as conn:
            config.attributes["connection"] = conn
            command.upgrade(config, "head")
        with store.begin() as db:
            db.add(User(username=username, display_name=username, password_hash="unused"))
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: campus_import.import_pack(pack, username, store), range(2)))
        assert results[0]["ids"] == results[1]["ids"]
        assert sorted(r["created"] for r in results) == [0, 2]
        with store() as db:
            assert db.scalar(select(func.count()).select_from(SearchOutbox)
                             .where(SearchOutbox.note_id.in_(results[0]["ids"].values()))) == 2
    finally:
        with store.begin() as db:
            ids = list(db.scalars(select(Note.id).where(Note.seed_key.in_(keys))))
            for model in (SearchOutbox, NoteImage):
                db.execute(delete(model).where(model.note_id.in_(ids)))
            db.execute(delete(Note).where(Note.id.in_(ids)))
            db.execute(delete(User).where(User.username == username))
        engine.dispose()
