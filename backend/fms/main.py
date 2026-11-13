from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
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

    return app
