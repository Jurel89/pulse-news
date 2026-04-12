from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, Request
from sqlalchemy import func, or_, select

from app.auth import require_authenticated_user
from app.deps import DbSession
from app.models import AuditEvent
from app.schemas import AuditEventListResponse, AuditEventSummary

audit_router = APIRouter(prefix="/audit", tags=["audit"])


@audit_router.get("", response_model=AuditEventListResponse)
def list_audit_events(
    request: Request,
    db: DbSession,
    action: str | None = None,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> AuditEventListResponse:
    require_authenticated_user(request, db)

    statement = select(AuditEvent).order_by(AuditEvent.created_at.desc())

    if action is not None:
        normalized_action = action.strip()
        if normalized_action:
            statement = statement.where(AuditEvent.action == normalized_action)

    if search is not None:
        normalized_search = search.strip().lower()
        if normalized_search:
            pattern = f"%{normalized_search}%"
            statement = statement.where(
                or_(
                    func.lower(AuditEvent.action).like(pattern),
                    func.lower(func.coalesce(AuditEvent.actor_email, "")).like(pattern),
                    func.lower(AuditEvent.entity_type).like(pattern),
                    func.lower(AuditEvent.entity_id).like(pattern),
                    func.lower(AuditEvent.summary).like(pattern),
                )
            )

    if date_from is not None:
        start_of_day = datetime.combine(date_from, time.min, tzinfo=UTC)
        statement = statement.where(AuditEvent.created_at >= start_of_day)

    if date_to is not None:
        end_of_day = datetime.combine(date_to, time.min, tzinfo=UTC)
        next_day = end_of_day + timedelta(days=1)
        statement = statement.where(AuditEvent.created_at < next_day)

    events = db.scalars(statement).all()
    return AuditEventListResponse(
        items=[AuditEventSummary.model_validate(event) for event in events]
    )
