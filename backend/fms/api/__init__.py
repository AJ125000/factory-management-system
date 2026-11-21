from fastapi import APIRouter

from . import (
    auth,
    backups,
    exports,
    machines,
    production,
    rates,
    reports,
    settings,
    system,
    worker_types,
    workers,
)

router = APIRouter(prefix="/api")
for module in (
    system,
    auth,
    settings,
    worker_types,
    workers,
    machines,
    rates,
    production,
    reports,
    exports,
    backups,
):
    router.include_router(module.router)
