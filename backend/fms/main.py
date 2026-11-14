from __future__ import annotations

import logging
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

log = logging.getLogger("fms")

# The only API paths that work without logging in.
PUBLIC_API = frozenset({"/api/health", "/api/auth/status", "/api/auth/setup", "/api/auth/login"})


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    run_migrations(settings.database_url)
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        log.info("FMS %s started, data in %s", __version__, settings.data_dir)
        yield
        engine.dispose()

    app = FastAPI(title="Kota Stone FMS", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.login_throttle = auth.LoginThrottle()
    app.include_router(router)

    def _logged_in_device(token: str) -> str | None:
        with app.state.session_factory() as session:
            device = auth.device_for_token(session, token)
            if device is None:
                return None
            auth.touch(session, device)
            return device.id

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
