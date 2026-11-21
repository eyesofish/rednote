import os
from functools import lru_cache

from elasticsearch import ApiError, Elasticsearch


@lru_cache(maxsize=1)
def get_client() -> Elasticsearch:
    return Elasticsearch(
        os.getenv("ES_URL", "http://search:9200"),
        request_timeout=2,
        max_retries=0,
        retry_on_timeout=False,
    )


def index_name() -> str:
    return os.getenv("SEARCH_INDEX", "rednote-notes-v1")


def error_type(error: ApiError) -> str:
    body = error.body if isinstance(error.body, dict) else {}
    reason = body.get("error")
    return reason.get("type", "") if isinstance(reason, dict) else ""


def ensure_index(client: Elasticsearch) -> None:
    if client.indices.exists(index=index_name()):
        return
    text_field = {"type": "text", "analyzer": "note_text"}
    settings = {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "refresh_interval": "1s",
        "analysis": {
            "tokenizer": {"characters": {"type": "ngram", "min_gram": 1, "max_gram": 1}},
            "analyzer": {"note_text": {"type": "custom", "tokenizer": "characters"}},
        },
    }
    properties = {
        "note_id": {"type": "long"},
        "version": {"type": "long"},
        "deleted": {"type": "boolean"},
        "title": text_field,
        "body": text_field,
        "published_at": {"type": "date"},
        "cover_url": {"type": "keyword", "index": False},
        "author_id": {"type": "long"},
        "author_name": {"type": "keyword", "index": False},
    }
    try:
        client.indices.create(
            index=index_name(), settings=settings,
            mappings={"dynamic": "strict", "properties": properties},
        )
    except ApiError as error:
        if error_type(error) != "resource_already_exists_exception":
            raise


class InvalidSnapshot(ValueError):
    """An immutable event cannot be represented as a search document."""


def apply_snapshot(client: Elasticsearch, snapshot: dict) -> str:
    """Index the immutable event or recognize a previously delivered newer/equal version."""
    if not isinstance(snapshot, dict) or type(snapshot.get("deleted")) is not bool:
        raise InvalidSnapshot("missing deletion flag")
    for field in ("note_id", "version"):
        if type(snapshot.get(field)) is not int or snapshot[field] < 1:
            raise InvalidSnapshot(f"invalid {field}")
    if not snapshot["deleted"]:
        required = {"title", "body", "published_at", "cover_url", "author_id", "author_name"}
        missing = required.difference(snapshot)
        if missing:
            raise InvalidSnapshot("missing fields: " + ", ".join(sorted(missing)))
    try:
        client.index(
            index=index_name(), id=snapshot["note_id"], version=snapshot["version"],
            version_type="external", document=snapshot,
        )
    except ApiError as error:
        if error.status_code == 409 and error_type(error) == "version_conflict_engine_exception":
            return "superseded"
        raise
    return "applied"


class IncompleteSearch(Exception):
    """At least one shard did not provide complete results."""


def search_notes(client: Elasticsearch, keyword: str) -> list[dict]:
    tiers = []
    for field, score in (("title", 2), ("body", 1)):
        phrase = {"match_phrase": {field: {"query": keyword, "slop": 0}}}
        tiers.append({"constant_score": {"filter": phrase, "boost": score}})
    query = {
        "bool": {
            "filter": [{"term": {"deleted": False}}],
            "must": [{"dis_max": {"queries": tiers, "tie_breaker": 0}}],
        }
    }
    fields = ["note_id", "title", "cover_url", "published_at", "author_id", "author_name"]
    response = client.search(
        index=index_name(), query=query, source=fields, size=100,
        sort=[{"_score": "desc"}, {"published_at": "desc"}, {"note_id": "desc"}],
        allow_partial_search_results=False, timeout="1500ms",
    )
    if response["timed_out"] or response["_shards"]["failed"]:
        raise IncompleteSearch
    items = []
    for hit in response["hits"]["hits"]:
        source = dict(hit["_source"])
        source["id"] = source.pop("note_id")
        items.append(source)
    return items
