from __future__ import annotations

from fastapi import APIRouter

from app.api.api_keys import api_keys_router
from app.api.audit import audit_router
from app.api.auth import auth_router
from app.api.email_templates import email_templates_router
from app.api.newsletters import newsletters_router
from app.api.providers import providers_router
from app.api.public import public_router
from app.api.runs import runs_router
from app.api.webhooks import webhooks_router
from app.auth import get_operation_mode_state
from app.config import get_settings
from app.deps import DbSession
from app.schemas import HealthResponse

api_router = APIRouter(prefix="/api")
api_router.include_router(api_keys_router)
api_router.include_router(audit_router)
api_router.include_router(auth_router)
api_router.include_router(email_templates_router)
api_router.include_router(newsletters_router)
api_router.include_router(providers_router)
api_router.include_router(public_router)
api_router.include_router(runs_router)
api_router.include_router(webhooks_router)


@api_router.get("/health", response_model=HealthResponse, tags=["system"])
def health(db: DbSession) -> HealthResponse:
    settings = get_settings()
    operation_modes = get_operation_mode_state(db)
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.environment,
        ai_generation_mode=operation_modes.ai_generation_mode,
        email_delivery_mode=operation_modes.email_delivery_mode,
    )
