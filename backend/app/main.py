import logging
import os
from contextvars import ContextVar
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from sqlalchemy import event, select
from sqlalchemy.exc import SQLAlchemyError

from app import auth, notes
from app.auth import DB
from app.db import engine
from app.models import User


logger = logging.getLogger("uvicorn.error")
statement_count: ContextVar[dict[str, int] | None] = ContextVar("statement_count", default=None)


@event.listens_for(engine, "before_cursor_execute")
def count_statement(conn, cursor, statement, parameters, context, executemany):
    counter = statement_count.get()
    if counter is not None:
        counter["sql"] += 1


def create_app() -> FastAPI:
    app = FastAPI(title="图文笔记社区", version="1.0")
    app.include_router(auth.router, prefix="/api")
    app.include_router(notes.router, prefix="/api")

    if os.getenv("SQL_REQUEST_TRACE") == "1":
        @app.middleware("http")
        async def trace_sql(request: Request, call_next):
            request_id = uuid4().hex
            counter = {"sql": 0}
            token = statement_count.set(counter)
            try:
                response = await call_next(request)
                response.headers["X-Request-ID"] = request_id
                response.headers["X-SQL-Statements"] = str(counter["sql"])
                logger.info("request_id=%s method=%s path=%s sql=%d", request_id, request.method,
                            request.url.path, counter["sql"])
                return response
            finally:
                statement_count.reset(token)

    @app.get("/api/health")
    def health(db: DB):
        try:
            db.execute(select(User.id).limit(1)).first()
        except SQLAlchemyError:
            raise HTTPException(503, "数据库尚未就绪")
        return {"status": "ok"}

    return app


app = create_app()
