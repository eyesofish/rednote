"""Single-consumer transactional outbox relay; use --help for local inspection."""
import argparse
import json
import logging
import time
from dataclasses import dataclass
from datetime import timedelta

from elasticsearch import ApiError
from elastic_transport import TransportError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db import SessionLocal, utcnow
from app.models import SearchOutbox
from app.search.index import InvalidSnapshot, apply_snapshot, ensure_index, error_type, get_client, index_name

log = logging.getLogger("rednote.worker")


@dataclass(frozen=True)
class Delivery:
    id: int
    snapshot: dict


def next_pending() -> Delivery | None:
    with SessionLocal() as db:
        row = db.execute(
            select(SearchOutbox.id, SearchOutbox.snapshot)
            .where(SearchOutbox.status == "pending", SearchOutbox.next_attempt_at <= utcnow())
            .order_by(SearchOutbox.next_attempt_at, SearchOutbox.id)
            .limit(1)
        ).first()
        return Delivery(row.id, row.snapshot) if row else None


def record_result(event: Delivery, status: str, error: str | None = None) -> None:
    with SessionLocal.begin() as db:
        row = db.get(SearchOutbox, event.id, with_for_update=True)
        if row.status != "pending":
            return
        row.status = status
        row.attempts += 1
        row.last_error = error
        if status == "pending":
            delay = (0.5, 1, 2)[min(row.attempts - 1, 2)]
            row.next_attempt_at = utcnow() + timedelta(seconds=delay)


def deliver(event: Delivery, client) -> None:
    # No database transaction spans the search request.
    try:
        result = apply_snapshot(client, event.snapshot)
    except InvalidSnapshot as exc:
        record_result(event, "failed", str(exc))
        log.error("event=%d invalid snapshot: %s", event.id, exc)
        return
    except (ApiError, TransportError) as exc:
        reason = type(exc).__name__
        status = "pending"
        if isinstance(exc, ApiError):
            reason = f"{exc.status_code}:{error_type(exc)}"
            if exc.status_code == 400:
                status = "failed"
        record_result(event, status, reason)
        log.warning("event=%d version=%d status=%s error=%s", event.id, event.snapshot["version"], status, reason)
        return
    record_result(event, "done")
    log.info("event=%d version=%d result=%s", event.id, event.snapshot["version"], result)


def run() -> None:
    client = get_client()
    initialized = False
    while True:
        try:
            if not initialized:
                ensure_index(client)
                initialized = True
            event = next_pending()
            if event:
                deliver(event, client)
            else:
                time.sleep(0.25)
        except (ApiError, TransportError, SQLAlchemyError) as exc:
            log.warning("poll postponed: %s", type(exc).__name__)
            time.sleep(1)


def inspect_event(note_id: int, version: int) -> dict:
    with SessionLocal() as db:
        row = db.scalar(select(SearchOutbox).where(
            SearchOutbox.note_id == note_id, SearchOutbox.version == version,
        ))
        if row is None:
            raise SystemExit("No event with that note ID and version")
        return {"event_id": row.id, "note_id": row.note_id, "version": row.version,
                "status": row.status, "attempts": row.attempts, "last_error": row.last_error}


def replay(event_id: int) -> dict:
    with SessionLocal() as db:
        event = db.get(SearchOutbox, event_id)
        if event is None:
            raise SystemExit("Unknown event ID")
        snapshot = event.snapshot
    result = apply_snapshot(get_client(), snapshot)
    return {"event_id": event_id, "version": snapshot["version"], "result": result}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command")
    inspection = commands.add_parser("event", help="Look up an outbox delivery")
    inspection.add_argument("note_id", type=int)
    inspection.add_argument("version", type=int)
    retry = commands.add_parser("replay", help="Submit a saved snapshot to the index again")
    retry.add_argument("event_id", type=int)
    commands.add_parser("refresh", help="Wait for index visibility (test barrier)")
    projection = commands.add_parser("projection", help="Inspect a raw indexed document by note ID")
    projection.add_argument("note_id", type=int)
    args = parser.parse_args()
    if args.command == "event":
        result = inspect_event(args.note_id, args.version)
    elif args.command == "replay":
        result = replay(args.event_id)
    elif args.command == "refresh":
        result = get_client().indices.refresh(index=index_name()).body
    elif args.command == "projection":
        result = get_client().get(index=index_name(), id=args.note_id).body
    else:
        run()
        return
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("elastic_transport.transport").setLevel(logging.WARNING)
    main()
