from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from . import __version__
from .api import router
from .api.auth import bearer_token
from .config import Settings
from .db import make_engine, make_session_factory, run_migrations
from .errors import FMSError
from .services import auth
from .services.backups import BackupScheduler
from .services.settings import get_settings

log = logging.getLogger("fms")

# Names the hub answers to. A web page can't trick a browser into talking to the hub
# under another name (DNS rebinding) - e.g. to claim a fresh install's password.
# FMS_ALLOWED_HOSTS adds more (comma-separated) for unusual setups.
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "testserver"})


def host_allowed(host_header: str) -> bool:
    host = host_header.strip().lower()
    if host.startswith("["):  # [::1]:8765
        host = host[1 : host.find("]")]
    elif host.count(":") == 1:
        host = host.split(":", 1)[0]
    extra = {h.strip().lower() for h in os.environ.get("FMS_ALLOWED_HOSTS", "").split(",") if h}
    return host in LOCAL_HOSTS or host in extra or host.endswith(".ts.net")


# The only API paths that work without logging in.
PUBLIC_API = frozenset({"/api/health", "/api/auth/status", "/api/auth/setup", "/api/auth/login"})


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    run_migrations(settings.database_url)
    engine = make_engine(settings.database_url)

    def backup_copy_dir() -> str:
        with app.state.session_factory() as session:
            return get_settings(session).backup_copy_dir.strip()

    scheduler = BackupScheduler(settings.db_path, settings.data_dir, backup_copy_dir)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        log.info("FMS %s started, data in %s", __version__, settings.data_dir)
        if settings.auto_backups:
            scheduler.start()
        yield
        scheduler.stop()
        app.state.engine.dispose()

    app = FastAPI(title="Kota Stone FMS", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.login_throttle = auth.LoginThrottle()
    app.state.backup_scheduler = scheduler
    app.include_router(router)

    def _logged_in_device(token: str) -> str | None:
        with app.state.session_factory() as session:
            device = auth.device_for_token(session, token)
            if device is None:
                return None
            auth.touch(session, device)
            return device.id

    @app.middleware("http")
    async def _require_known_host(request: Request, call_next):
        if not host_allowed(request.headers.get("host", "")):
            log.warning("Refused a request for unknown host %r", request.headers.get("host"))
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "bad_host", "message": "Unknown host.", "details": {}}},
            )
        return await call_next(request)

    @app.middleware("http")
    async def _require_login(request: Request, call_next):
        """Every /api request needs a logged-in device, except the few listed in PUBLIC_API."""
        path = request.url.path
        if (path == "/api" or path.startswith("/api/")) and path not in PUBLIC_API:
            token = bearer_token(request)
            device_id = await run_in_threadpool(_logged_in_device, token) if token else None
            if device_id is None:
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": {
                            "code": "unauthorized",
                            "message": "Please log in.",
                            "details": {"reason": "login_required"},
                        }
                    },
                )
            request.state.device_id = device_id
        return await call_next(request)

    @app.exception_handler(FMSError)
    async def _domain_error(_request: Request, exc: FMSError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Full details go to the log on the laptop; the app shows a calm message.
        log.exception("Unexpected error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "server_error",
                    "message": "Something went wrong on the laptop. It has been noted in the log.",
                    "details": {},
                }
            },
        )

    @app.exception_handler(IntegrityError)
    async def _integrity_error(_request: Request, exc: IntegrityError) -> JSONResponse:
        log.warning("Integrity error: %s", exc.orig)
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "conflict",
                    "message": "This change conflicts with existing data.",
                    "details": {},
                }
            },
        )

    _serve_frontend(app, settings.static_dir)
    return app


def _serve_frontend(app: FastAPI, static_dir: Path) -> None:
    """Serve the built React app (frontend/ builds into fms/static) with SPA fallback."""
    index = static_dir / "index.html"
    if not index.is_file():
        log.warning("Frontend not built (%s missing); serving the API only", index)
        return
    root = static_dir.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    async def _spa(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            # Built assets have content hashes in their names, so they can be cached forever.
            # Everything else (sw.js, manifest, index.html, icons) must be re-checked, so a
            # new version of the app reaches the phone as soon as the hub has it.
            cache = (
                "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
            )
            return FileResponse(candidate, headers={"Cache-Control": cache})
        if "." in path.rsplit("/", 1)[-1]:
            # A missing *file* (e.g. favicon.ico, a stale asset) is a real 404, not a screen.
            raise HTTPException(status_code=404)
        # Any other path is a screen inside the app; always fetch the latest index.html.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
