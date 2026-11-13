from fastapi import APIRouter

from . import production, rates, reports, settings, system, worker_types, workers

router = APIRouter(prefix="/api")
for module in (system, settings, worker_types, workers, rates, production, reports):
    router.include_router(module.router)
