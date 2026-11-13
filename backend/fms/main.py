from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.exc import IntegrityError

from . import __version__
from .api import router
from .config import Settings
from .db import make_engine, make_session_factory, run_migrations
from .errors import FMSError

log = logging.getLogger("fms")


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
    app.include_router(router)

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
            cache = "public, max-age=31536000, immutable" if path.startswith("assets/") else None
            return FileResponse(candidate, headers={"Cache-Control": cache} if cache else None)
        # Any other path is a screen inside the app; always fetch the latest index.html.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
