from __future__ import annotations

from fastapi import APIRouter

from app.api.auth import auth_router
from app.api.newsletters import newsletters_router
from app.api.public import public_router
from app.api.runs import runs_router
from app.api.webhooks import webhooks_router
from app.config import get_settings
from app.schemas import HealthResponse

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(newsletters_router)
api_router.include_router(public_router)
api_router.include_router(runs_router)
api_router.include_router(webhooks_router)


@api_router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.environment,
    )
