from elasticsearch import ApiError
from elastic_transport import TransportError
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from .index import IncompleteSearch, get_client, search_notes

router = APIRouter()


@router.get("/search")
def search(q: str = Query(min_length=1, max_length=128), client=Depends(get_client)):
    keyword = q.strip()
    if not keyword:
        return JSONResponse({"code": "EMPTY_QUERY"}, status_code=422)
    try:
        return {"items": search_notes(client, keyword)}
    except (TransportError, ApiError, IncompleteSearch):
        return JSONResponse({"code": "SEARCH_UNAVAILABLE"}, status_code=503)
