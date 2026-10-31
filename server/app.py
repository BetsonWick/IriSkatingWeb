"""IriSkating site server: static landing + bookings API with admin auth.

Runs behind Caddy on the VPS (see deploy/DEPLOY.md). Configuration comes
from environment variables (see .env.example):

- ADMIN_USERNAME / ADMIN_PASSWORD_HASH — the single admin account
- SESSION_SECRET — HMAC key for session cookies
- COOKIE_SECURE — set the Secure flag on the session cookie (true behind HTTPS)
- DATABASE_PATH — SQLite file for booking requests
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from server.auth import create_session_token, verify_password, verify_session_token
from server.db import BookingsDB

SESSION_COOKIE = "iriskating_session"
_BASE_DIR = Path(__file__).resolve().parent.parent

# (name of the bucket, allowed hits, window seconds)
_RATE_LIMITS: dict[str, tuple[int, int]] = {
    "login": (10, 300),
    "booking": (30, 600),
}
_rate_buckets: dict[str, deque[float]] = defaultdict(deque)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    admin_username: str = "iren"
    admin_password_hash: str = ""
    session_secret: str = "dev-secret-change-me"
    cookie_secure: bool = True
    database_path: Path = Path("data/site.db")


def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_base_dir() -> Path:
    return _BASE_DIR


def check_rate_limit(bucket: str, client_ip: str) -> None:
    """Sliding-window limiter; raises 429 when the bucket overflows."""
    limit, window = _RATE_LIMITS[bucket]
    now = time.monotonic()
    hits = _rate_buckets[f"{bucket}:{client_ip}"]
    while hits and now - hits[0] > window:
        hits.popleft()
    if len(hits) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests, try later")
    hits.append(now)


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_current_user(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> str:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    username = verify_session_token(token, settings.session_secret)
    if username is None:
        raise HTTPException(status_code=401, detail="Session expired")
    return username


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class BookingRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    contact: str = Field(min_length=3, max_length=120)
    program: Literal["individual", "group", "video", "fitness"]
    preferred_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    preferred_time: Literal["morning", "afternoon", "evening", "any"]
    comment: str = Field(default="", max_length=500)


class StatusUpdate(BaseModel):
    status: Literal["new", "confirmed", "cancelled"]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    app.state.db = BookingsDB(get_settings().database_path)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="IriSkating site",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.post("/api/login")
    def login(
        payload: LoginRequest,
        request: Request,
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> JSONResponse:
        check_rate_limit("login", get_client_ip(request))
        if payload.username != settings.admin_username or not verify_password(
            payload.password, settings.admin_password_hash
        ):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = create_session_token(payload.username, settings.session_secret)
        response = JSONResponse({"ok": True, "username": payload.username})
        response.set_cookie(
            SESSION_COOKIE,
            token,
            max_age=7 * 24 * 3600,
            httponly=True,
            samesite="lax",
            secure=settings.cookie_secure,
            path="/",
        )
        return response

    @app.post("/api/logout")
    def logout(response: Response) -> dict[str, bool]:
        response.delete_cookie(SESSION_COOKIE, path="/")
        return {"ok": True}

    @app.get("/api/me")
    def me(user: Annotated[str, Depends(get_current_user)]) -> dict[str, str]:
        return {"username": user}

    @app.post("/api/bookings")
    def create_booking(
        payload: BookingRequest,
        request: Request,
    ) -> dict[str, Any]:
        check_rate_limit("booking", get_client_ip(request))
        booking_id: int = app.state.db.add(
            name=payload.name.strip(),
            contact=payload.contact.strip(),
            program=payload.program,
            preferred_date=payload.preferred_date,
            preferred_time=payload.preferred_time,
            comment=payload.comment.strip(),
        )
        return {"ok": True, "id": booking_id}

    @app.get("/api/bookings")
    def list_bookings(
        _: Annotated[str, Depends(get_current_user)],
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = app.state.db.list()
        return result

    @app.patch("/api/bookings/{booking_id}")
    def update_booking(
        booking_id: int,
        payload: StatusUpdate,
        _: Annotated[str, Depends(get_current_user)],
    ) -> dict[str, Any]:
        updated: bool = app.state.db.set_status(booking_id, payload.status)
        if not updated:
            raise HTTPException(status_code=404, detail="Booking not found")
        return {"ok": True}

    # ---------- static site ----------

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(get_base_dir() / "index.html")

    @app.get("/admin", include_in_schema=False)
    def admin_page() -> FileResponse:
        return FileResponse(get_base_dir() / "admin.html")

    @app.get("/admin.html", include_in_schema=False)
    def admin_page_html() -> FileResponse:
        # относительная ссылка admin.html из шапки должна работать и на проде
        return FileResponse(get_base_dir() / "admin.html")

    @app.get("/index.html", include_in_schema=False)
    def index_html() -> FileResponse:
        return FileResponse(get_base_dir() / "index.html")

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon() -> FileResponse:
        return FileResponse(get_base_dir() / "assets" / "favicon.svg", media_type="image/svg+xml")

    app.mount("/css", StaticFiles(directory=get_base_dir() / "css"), name="css")
    app.mount("/js", StaticFiles(directory=get_base_dir() / "js"), name="js")
    app.mount("/assets", StaticFiles(directory=get_base_dir() / "assets"), name="assets")

    return app


app = create_app()
