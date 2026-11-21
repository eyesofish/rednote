from unittest.mock import Mock

import pytest
from elastic_transport import ApiResponseMeta, ConnectionTimeout, NodeConfig
from elasticsearch import ApiError
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.search.index import apply_snapshot, get_client
from app.search.router import router


def es_error(status, kind):
    meta = ApiResponseMeta(status, "1.1", {}, 0.01, NodeConfig("http", "localhost", 9200))
    return ApiError(kind, meta, {"error": {"type": kind}})


@pytest.fixture
def endpoint():
    app = FastAPI()
    client = Mock()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_client] = lambda: client
    with TestClient(app) as http:
        yield http, client


def test_search_distinguishes_empty_and_service_failures(endpoint):
    http, client = endpoint
    empty = {"hits": {"hits": []}, "_shards": {"failed": 0}, "timed_out": False}
    client.search.side_effect = [
        empty, ConnectionTimeout("down"), {**empty, "timed_out": True},
        {**empty, "_shards": {"failed": 1}}, es_error(503, "unavailable_shards_exception"),
    ]
    assert http.get("/api/search", params={"q": "火山"}).json() == {"items": []}
    for _ in range(4):
        response = http.get("/api/search", params={"q": "火山"})
        assert response.status_code == 503
        assert response.json()["code"] == "SEARCH_UNAVAILABLE"


def test_snapshot_writes_external_version_and_only_swallows_version_conflicts():
    client = Mock()
    snapshot = {"note_id": 81, "version": 5, "deleted": True}
    assert apply_snapshot(client, snapshot) == "applied"
    fields = client.index.call_args.kwargs
    assert (fields["id"], fields["version"], fields["version_type"]) == (81, 5, "external")
    assert fields["document"] == snapshot
    client.index.side_effect = es_error(409, "version_conflict_engine_exception")
    assert apply_snapshot(client, snapshot) == "superseded"
    client.index.side_effect = es_error(409, "different_conflict")
    with pytest.raises(ApiError):
        apply_snapshot(client, snapshot)


def test_blank_search_never_queries_engine(endpoint):
    http, client = endpoint
    assert http.get("/api/search", params={"q": "  "}).status_code == 422
    client.search.assert_not_called()


def test_delivery_classifies_malformed_snapshot_and_transient_error(monkeypatch):
    from app import worker

    record = Mock()
    monkeypatch.setattr(worker, "record_result", record)
    client = Mock()
    malformed = worker.Delivery(12, {"note_id": 2})
    worker.deliver(malformed, client)
    record.assert_called_once_with(malformed, "failed", "missing deletion flag")
    client.index.assert_not_called()

    valid = worker.Delivery(13, {"note_id": 2, "version": 4, "deleted": True})
    client.index.side_effect = ConnectionTimeout("down")
    worker.deliver(valid, client)
    record.assert_called_with(valid, "pending", "ConnectionTimeout")
    client.index.side_effect = es_error(400, "document_parsing_exception")
    worker.deliver(valid, client)
    record.assert_called_with(valid, "failed", "400:document_parsing_exception")
