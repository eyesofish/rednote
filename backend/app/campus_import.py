"""Validate, import and check a campus-notes-v1 ZIP from the operator's terminal."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

from app.campus_pack import load_pack


PREFIX = "campus-notes-v1:"


def check_content(db, note, entry, *, lock=False):
    from sqlalchemy import select
    from app.models import NoteImage

    if note.deleted_at is not None:
        raise ValueError(f"{entry.id} 已被删除，保留删除状态")
    if (note.title, note.body) != (entry.title.strip(), entry.body.strip()):
        raise ValueError(f"{entry.id} 与已导入的标题或正文不同")
    query = select(NoteImage.media_type, NoteImage.content).where(NoteImage.note_id == note.id)
    images = db.execute(query.with_for_update() if lock else query).all()
    if images != [(entry.media_type, entry.image_bytes)]:
        raise ValueError(f"{entry.id} 与已导入的配图不同")


def import_pack(pack, author, factory=None):
    from sqlalchemy import select
    from app.db import SessionLocal
    from app.models import Note, User
    from app.notes import create_note_record

    factory = factory or SessionLocal
    ids = {}
    created = 0
    with factory.begin() as db:
        # An import that uses this account waits for its previous import to commit.
        user = db.scalar(select(User).where(User.username == author).with_for_update())
        if user is None:
            raise ValueError(f"找不到导入账号 {author}")
        for entry in pack.notes:
            key = PREFIX + entry.id
            note = db.scalar(select(Note).where(Note.seed_key == key).with_for_update())
            if note is None:
                note = create_note_record(db, user, entry.title, entry.body,
                                          [(entry.media_type, entry.image_bytes)], seed_key=key)
                created += 1
            else:
                if note.author_id != user.id:
                    raise ValueError(f"{entry.id} 属于其他作者，不能以 {author} 导入")
                check_content(db, note, entry, lock=True)
            ids[entry.id] = note.id
    return {"created": created, "reused": len(ids) - created, "ids": ids}


def verify_pack(pack, *, factory=None, client=None, timeout=30):
    from elastic_transport import TransportError
    from elasticsearch import ApiError
    from sqlalchemy import select
    from app.db import SessionLocal
    from app.models import Note
    from app.search.index import IncompleteSearch, get_client, search_notes

    factory = factory or SessionLocal
    ids = {}
    with factory() as db:
        by_key = {n.seed_key: n for n in db.scalars(
            select(Note).where(Note.seed_key.in_([PREFIX + row.id for row in pack.notes]))
        )}
        for entry in pack.notes:
            note = by_key.get(PREFIX + entry.id)
            if note is None:
                raise ValueError(f"{entry.id} 尚未导入")
            check_content(db, note, entry)
            ids[entry.id] = note.id

    client = get_client() if client is None else client
    deadline = time.monotonic() + timeout
    last_problem = "在等待上限内未完成所有查询"
    while True:
        report = {}
        problem = ""
        for case in pack.cases:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            expected = [ids[key] for key in (case.title_id, case.body_only_id) if key]
            try:
                actual = [row["id"] for row in search_notes(
                    client.options(request_timeout=min(2, remaining)), case.query,
                )]
            except (TransportError, ApiError, IncompleteSearch) as error:
                problem = f"{case.query}：搜索服务未返回完整结果（{type(error).__name__}）"
                break
            if actual != expected:
                problem = f"{case.query}：预期笔记 ID {expected}，实际为 {actual}"
                break
            report[case.query] = actual
        if not problem and len(report) == len(pack.cases) and time.monotonic() <= deadline:
            return {"verified": len(ids), "search_cases": report}
        if problem:
            last_problem = problem
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError(f"搜索验收超时：{last_problem}")
        time.sleep(min(0.25, remaining))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="action", required=True)
    for name in ("validate", "import", "verify"):
        command = subcommands.add_parser(name)
        command.add_argument("pack", type=Path)
        command.add_argument("--stage", choices=("pilot", "final"), default="final")
        if name == "import":
            command.add_argument("--author", required=True)
    args = parser.parse_args(argv)
    try:
        pack = load_pack(args.pack, args.stage)
        result = {"notes": len(pack.notes), "cases": len(pack.cases), "warnings": pack.warnings}
        if args.action == "validate":
            print(json.dumps(result, ensure_ascii=False))
            return 0
    except (ValueError, OSError) as error:
        print(error, file=sys.stderr)
        return 1

    from sqlalchemy.exc import SQLAlchemyError
    try:
        if args.action == "import":
            result.update(import_pack(pack, args.author))
        if args.action == "verify":
            timeout = float(os.getenv("SYNC_TIMEOUT_SECONDS", "30"))
            if not 0 < timeout <= 30:
                raise ValueError("SYNC_TIMEOUT_SECONDS 必须大于 0 且不超过 30")
            result.update(verify_pack(pack, timeout=timeout))
    except (ValueError, OSError) as error:
        print(error, file=sys.stderr)
        return 1
    except SQLAlchemyError as error:
        # Detailed SQL exceptions may contain the uploaded note or binary image content.
        print(f"数据库操作失败（{type(error).__name__}），请核对连接、迁移和并发导入状态后重试", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
