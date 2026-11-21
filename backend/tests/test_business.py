"""Exercise HTTP routes through FastAPI. Set TEST_DATABASE_URL for InnoDB locking tests."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app import seed
from app.auth import hash_password
from app.db import get_db
from app.main import create_app
from app.models import Favorite, Note, SearchOutbox, User


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    default_db = tmp_path_factory.mktemp("business") / "test.db"
    engine = create_engine(os.getenv("TEST_DATABASE_URL", f"sqlite:///{default_db.as_posix()}"))
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        command.upgrade(config, "head")
    factory = sessionmaker(engine, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture(scope="module")
def accounts(store):
    suffix = uuid4().hex[:8]
    names = [f"{name}-{suffix}" for name in ("writer", "reader")]
    with store.begin() as db:
        for name in names:
            db.add(User(username=name, display_name=name, password_hash=hash_password("local-test")))
    return names


@pytest.fixture()
def clients(store, accounts):
    api = create_app()

    def session():
        with store() as db:
            yield db

    api.dependency_overrides[get_db] = session
    with TestClient(api) as author, TestClient(api) as reader:
        for client, name in zip((author, reader), accounts, strict=True):
            logged = client.post("/api/sessions", json={"username": name, "password": "local-test"})
            assert logged.status_code == 200
            assert logged.json() == client.get("/api/me").json()
            assert "httponly" in logged.headers["set-cookie"].lower()
        yield author, reader


def post_note(client, title="旅行记录"):
    return client.post("/api/notes", data={"title": title, "body": "一份中文笔记"},
                       files={"images": ("sample.png", seed.sample_image("desk"), "image/png")})


def test_two_accounts_create_edit_delete_and_favorites(clients, store):
    author, reader = clients
    result = post_note(author)
    assert result.status_code == 201, result.text
    note = result.json()
    url = f"/api/notes/{note['id']}"
    bookmark = f"/api/me/favorites/{note['id']}"
    assert reader.get("/api/notes").json()["items"][0]["id"] == note["id"]
    assert reader.get(url).json()["body"] == "一份中文笔记"
    cover = reader.get(note["cover_url"])
    assert cover.headers["content-type"] == "image/png"
    assert cover.content == seed.sample_image("desk")
    assert reader.patch(url, data={"title": "不应该成功"}).status_code == 403
    assert reader.delete(url).status_code == 403
    assert reader.put(bookmark).status_code == reader.put(bookmark).status_code == 204
    assert reader.get(url).json()["is_favorite"] is True
    assert [item["id"] for item in reader.get("/api/me/favorites").json()["items"]] == [note["id"]]
    assert author.get("/api/me/favorites").json()["items"] == []
    assert reader.delete(bookmark).status_code == 204
    assert reader.get("/api/me/favorites").json()["items"] == []
    assert reader.put(bookmark).status_code == 204
    renamed = author.patch(url, data={"title": "另一篇笔记"})
    assert renamed.json()["images"] == note["images"]
    assert reader.get(url).json()["title"] == "另一篇笔记"
    assert author.delete(url).status_code == 204
    assert reader.get(url).status_code == reader.get(note["cover_url"]).status_code == 404
    assert reader.get("/api/me/favorites").json()["items"] == []
    assert all(item["id"] != note["id"] for item in reader.get("/api/notes").json()["items"])
    with store() as db:
        events = db.scalars(select(SearchOutbox).where(SearchOutbox.note_id == note["id"])
                            .order_by(SearchOutbox.version)).all()
        assert [event.snapshot.get("title") for event in events] == ["旅行记录", "另一篇笔记", None]
        assert events[-1].snapshot == {"note_id": note["id"], "version": 3, "deleted": True}
    session_cookie = author.cookies.get("rednote_session")
    assert author.delete("/api/sessions/current").status_code == 204
    author.cookies.set("rednote_session", session_cookie)
    assert author.get("/api/me").status_code == post_note(author).status_code == 401


def test_image_validation_and_replacement(clients):
    author, _ = clients
    note = post_note(author).json()
    url = f"/api/notes/{note['id']}"
    invalid = author.patch(url, data={"title": "无效更新"},
                           files={"images": ("fake.jpg", b"not an image", "image/jpeg")})
    assert invalid.status_code == 422
    assert author.get(url).json() == note
    updated = author.patch(url, files={"images": ("hill.png", seed.sample_image("hill"), "image/png")})
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert author.get(updated.json()["cover_url"]).content == seed.sample_image("hill")


def test_seed_repeat_preserves_changes(store, monkeypatch):
    monkeypatch.setattr(seed, "SessionLocal", store)
    seed.seed()
    with store.begin() as db:
        sample = db.scalars(select(Note).where(Note.seed_key == "interview")).one()
        sample_id = sample.id
        old_title = sample.title
        sample.title = "本地修改"
    try:
        seed.seed()
        with store() as db:
            assert db.get(Note, sample_id).title == "本地修改"
            assert db.scalar(select(func.count()).select_from(Note).where(Note.seed_key.is_not(None))) == 2
    finally:
        with store.begin() as db:
            db.get(Note, sample_id).title = old_title


def test_parallel_favorites_and_edits_are_serialized(clients, store):
    if store.kw["bind"].dialect.name != "mysql":
        pytest.skip("InnoDB row locks require TEST_DATABASE_URL to point at MySQL")
    author, reader = clients
    note = post_note(author).json()
    url = f"/api/notes/{note['id']}"
    with ThreadPoolExecutor(2) as pool:
        favorites = list(pool.map(lambda _: reader.put(f"/api/me/favorites/{note['id']}"), range(2)))
        edits = list(pool.map(lambda name: author.patch(url, data={"title": name}), ("一改", "二改")))
    assert [response.status_code for response in favorites] == [204, 204]
    assert all(response.status_code == 200 for response in edits)
    assert sorted(response.json()["version"] for response in edits) == [2, 3]
    with store() as db:
        assert db.scalar(select(func.count()).select_from(Favorite).where(Favorite.note_id == note["id"])) == 1
        versions = db.scalars(select(SearchOutbox.version).where(SearchOutbox.note_id == note["id"])
                              .order_by(SearchOutbox.version)).all()
        assert versions == [1, 2, 3]
