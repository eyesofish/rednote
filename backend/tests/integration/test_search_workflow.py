"""Acceptance tests against a running, seeded, isolated Compose project."""
import base64
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

import httpx
import pytest


pytestmark = pytest.mark.skipif(os.getenv("REDNOTE_LIVE") != "1", reason="requires the isolated Compose stack")
ROOT = Path(__file__).resolve().parents[3]
BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:18085").rstrip("/")
SYNC_TIMEOUT_SECONDS = float(os.getenv("SYNC_TIMEOUT_SECONDS", "30"))
# Original 4 x 4 test image. A valid PNG, including the IDAT checksum.
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAIAAAAmkwkpAAAAEklEQVR4nGP8/58BDpgQTHwcAGWfAgaNBKHBAAAAAElFTkSuQmCC")


def compose(*args, check=True):
    project = os.environ["COMPOSE_PROJECT_NAME"]
    assert project != "rednote", "select a separate test project and volumes"
    result = subprocess.run(
        ["docker", "compose", "--project-name", project, *map(str, args)],
        cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", timeout=120,
    )
    if check:
        assert result.returncode == 0, (result.stdout, result.stderr)
    return result


def worker_command(*args):
    output = compose("exec", "-T", "api", "python", "-m", "app.worker", *args)
    return json.loads(output.stdout)


def poll(label, read, predicate, started, budget=SYNC_TIMEOUT_SECONDS):
    deadline = started + budget
    last = None
    while (remaining := deadline - time.monotonic()) > 0:
        try:
            last = read(min(2.5, remaining))
            if predicate(last):
                elapsed = time.monotonic() - started
                assert elapsed <= budget, f"{label} completed too late: {elapsed:.3f}s"
                print(f"{label}: {elapsed:.3f}s, last={last}", flush=True)
                return last
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            last = str(error)
        time.sleep(min(0.25, max(deadline - time.monotonic(), 0)))
    pytest.fail(f"{label} exceeded {budget}s; elapsed={time.monotonic() - started:.3f}s; last={last}")


def search_ids(http, keyword, timeout=2.5):
    response = http.get("/api/search", params={"q": keyword}, timeout=timeout)
    response.raise_for_status()
    return [item["id"] for item in response.json()["items"]]


def await_ids(http, keyword, expected, started, label):
    return poll(label, lambda timeout: search_ids(http, keyword, timeout), lambda ids: ids == expected, started)


def wait_search_ready(http):
    def probe(timeout):
        response = http.get("/api/search", params={"q": "启动探针"}, timeout=timeout)
        return response.status_code, time.monotonic()

    _, ready_at = poll(
        "index responds to a query", probe, lambda result: result[0] == 200,
        time.monotonic(), budget=180,
    )
    return ready_at


def publish(http, title, body="一篇示例笔记。"):
    response = http.post(
        "/api/notes", data={"title": title, "body": body}, files=[("images", ("cover.png", PNG, "image/png"))],
    )
    saved_at = time.monotonic()
    assert response.status_code == 201, response.text
    return response.json()["id"], saved_at


def rename(http, note, new_title):
    response = http.patch(f"/api/notes/{note}", data={"title": new_title})
    saved_at = time.monotonic()
    assert response.status_code == 200, response.text
    return response.json()["version"], saved_at


@pytest.fixture
def http():
    with httpx.Client(base_url=BASE, timeout=5, trust_env=False) as client:
        login = client.post("/api/sessions", json={"username": "lune", "password": "notebook-demo"})
        login.raise_for_status()
        yield client


def test_chinese_ranking_and_edit(http):
    wait_search_ready(http)
    tag = uuid4().hex[:8]
    keyword, replacement = f"美团{tag}", f"字节{tag}"
    first, first_saved = publish(http, f"{keyword}一面复盘")
    second, second_saved = publish(http, "周末面试笔记", body=keyword * 12)
    separated, decoy_saved = publish(http, f"美食团{tag}")
    await_ids(http, keyword, [first, second], min(first_saved, second_saved), f"rank notes {first}/{second}, v1")
    # Ensure the third note was indexed before checking that noncontiguous characters do not match.
    await_ids(http, f"美食团{tag}", [separated], decoy_saved, f"index note {separated}, v1")
    assert search_ids(http, keyword) == [first, second]
    assert first in search_ids(http, "团")
    assert search_ids(http, f"火山{tag}") == []
    version, edited = rename(http, first, replacement)
    assert http.get(f"/api/notes/{first}").json()["title"] == replacement
    await_ids(http, replacement, [first], edited, f"note {first}, v{version}")
    await_ids(http, keyword, [second], edited, f"old keyword removed from note {first}, v{version}")
    print(worker_command("event", first, version))


def test_outage_and_historical_replay(http):
    wait_search_ready(http)
    tag = uuid4().hex[:8]
    old, middle, final = (word + tag for word in ["初稿", "中稿", "定稿"])
    victim_old, victim_edit, empty = (word + tag for word in ["公开", "撤回", "火山"])
    victim, victim_saved = publish(http, victim_old)
    await_ids(http, victim_old, [victim], victim_saved, f"index deletion fixture {victim}, v1")
    assert search_ids(http, empty) == []
    trace_ids = set()
    try:
        compose("stop", "search")
        for query in (victim_old, empty):
            response = http.get("/api/search", params={"q": query})
            assert response.status_code == 503
            assert response.json()["code"] == "SEARCH_UNAVAILABLE"
            assert response.headers["X-SQL-Statements"] == "0"
            trace_ids.add(response.headers["X-Request-ID"])
        assert len(trace_ids) == 2
        print(f"503 queries executed zero SQL statements: request IDs {sorted(trace_ids)}")
        live, _ = publish(http, old)
        middle_version, _ = rename(http, live, middle)
        final_version, _ = rename(http, live, final)
        detail = http.get(f"/api/notes/{live}")
        assert detail.json()["title"] == final
        assert int(detail.headers["X-SQL-Statements"]) > 0  # positive control for SQL instrumentation
        assert live in [item["id"] for item in http.get("/api/notes").json()["items"]]
        victim_edit_version, _ = rename(http, victim, victim_edit)
        assert http.delete(f"/api/notes/{victim}").status_code == 204
        assert http.get(f"/api/notes/{victim}").status_code == 404
    finally:
        compose("start", "search")
    recovered = wait_search_ready(http)
    await_ids(http, final, [live], recovered, f"recovery note {live}, v{final_version}")
    await_ids(http, victim_old, [], recovered, f"recovery deletion {victim}, v{victim_edit_version + 1}")
    # Its old title can disappear at the intermediate edit. Wait for the deletion itself.
    deletion_version = victim_edit_version + 1
    poll(
        f"recover deletion event for {victim}, v{deletion_version}",
        lambda _: worker_command("event", victim, deletion_version),
        lambda row: row["status"] == "done", recovered,
    )
    worker_command("refresh")
    removed = worker_command("projection", victim)
    assert removed["_version"] == deletion_version and removed["_source"]["deleted"] is True
    assert search_ids(http, victim_old) == search_ids(http, victim_edit) == []
    saved = worker_command("event", live, middle_version)
    for _ in range(2):
        replay = worker_command("replay", saved["event_id"])
        assert replay["result"] == "superseded", replay
        worker_command("refresh")
        assert search_ids(http, final) == [live]
        assert search_ids(http, old) == search_ids(http, middle) == []
    saved = worker_command("event", victim, victim_edit_version)
    assert worker_command("replay", saved["event_id"])["result"] == "superseded"
    worker_command("refresh")
    assert search_ids(http, victim_old) == search_ids(http, victim_edit) == []
    assert http.get(f"/api/notes/{victim}").status_code == 404
    print(f"replayed immutable event {saved['event_id']} after deletion v{deletion_version}")


def test_crash_after_index_before_acknowledgement(http):
    wait_search_ready(http)
    title = "提交窗口" + uuid4().hex[:8]
    # Stop the normal consumer, run its delivery with an abrupt exit exactly at the ack boundary.
    compose("stop", "worker")
    try:
        note, _ = publish(http, title)
        event = worker_command("event", note, 1)
        assert event["status"] == "pending"
        fault = (
            "import os,sys; from unittest.mock import patch; from app import worker; "
            "from app.search.index import get_client; from app.db import SessionLocal; "
            "from app.models import SearchOutbox; "
            "db=SessionLocal(); row=db.get(SearchOutbox,int(sys.argv[1])); "
            "event=worker.Delivery(row.id,row.snapshot); db.close(); "
            "patch.object(worker,'record_result',side_effect=lambda *args: os._exit(73)).start(); "
            "worker.deliver(event,get_client())"
        )
        crashed = compose("exec", "-T", "api", "python", "-c", fault, event["event_id"], check=False)
        assert crashed.returncode == 73, (crashed.stdout, crashed.stderr)
        assert worker_command("projection", note)["_source"]["title"] == title
        assert worker_command("event", note, 1)["status"] == "pending"
    finally:
        restarted = time.monotonic()
        compose("start", "worker")
    await_ids(http, title, [note], restarted, f"redelivery event {event['event_id']} v1")
    result = poll(
        f"acknowledge event {event['event_id']} v1",
        lambda _: worker_command("event", note, 1),
        lambda row: row["status"] == "done", restarted,
    )
    assert result["attempts"] >= 1
