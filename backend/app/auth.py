import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import get_db, utcnow
from app.models import LoginSession, User


router = APIRouter()
DB = Annotated[Session, Depends(get_db)]
COOKIE = "rednote_session"
CookieToken = Annotated[str | None, Cookie(alias=COOKIE)]
SESSION_TTL = timedelta(days=7)


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=32768, r=8, p=1, maxmem=64 * 1024**2)
    return f"scrypt:{salt.hex()}:{digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    _, salt, _ = encoded.split(":")
    return hmac.compare_digest(encoded, hash_password(password, bytes.fromhex(salt)))


def token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def maybe_user(db: DB, cookie: CookieToken = None) -> User | None:
    if not cookie:
        return None
    return db.scalar(
        select(User).join(LoginSession, LoginSession.user_id == User.id).where(
            LoginSession.token_hash == token_hash(cookie), LoginSession.expires_at > utcnow()
        )
    )


def require_user(user: Annotated[User | None, Depends(maybe_user)]) -> User:
    if user is None:
        raise HTTPException(401, "请先登录")
    return user


CurrentUser = Annotated[User, Depends(require_user)]
OptionalUser = Annotated[User | None, Depends(maybe_user)]


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


def profile(user: User) -> dict:
    return {"id": user.id, "username": user.username, "display_name": user.display_name}


@router.post("/sessions")
def login(data: Login, db: DB, response: Response, cookie: CookieToken = None):
    user = db.scalar(select(User).where(User.username == data.username))
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "用户名或密码不正确")
    if cookie:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(cookie)))
    raw = secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=token_hash(raw), user_id=user.id, expires_at=utcnow() + SESSION_TTL))
    db.commit()
    response.set_cookie(COOKIE, raw, httponly=True, samesite="lax", max_age=int(SESSION_TTL.total_seconds()))
    return profile(user)


@router.delete("/sessions/current", status_code=204)
def logout(db: DB, cookie: CookieToken = None) -> Response:
    if cookie:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(cookie)))
        db.commit()
    response = Response(status_code=204)
    response.delete_cookie(COOKIE, httponly=True, samesite="lax")
    return response


@router.get("/me")
def me(user: CurrentUser):
    return profile(user)
