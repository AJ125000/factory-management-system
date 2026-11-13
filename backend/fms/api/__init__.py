from fastapi import APIRouter

from . import production, rates, reports, system, worker_types, workers

router = APIRouter(prefix="/api")
for module in (system, worker_types, workers, rates, production, reports):
    router.include_router(module.router)
