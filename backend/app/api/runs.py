from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.auth import require_authenticated_user
from app.config import get_settings
from app.deps import DbSession
from app.email_delivery import retrieve_email_status
from app.models import NewsletterRun, NewsletterRunEvent
from app.schemas import (
    NewsletterRunEventSummary,
    NewsletterRunSummary,
    NewsletterSummary,
    RecipientSendOutcomeResponse,
    RunDetailResponse,
    RunListResponse,
    RunReconciliationResponse,
)

runs_router = APIRouter(prefix="/runs", tags=["runs"])


def get_run_or_404(db: DbSession, run_id: int) -> NewsletterRun:
    run = db.scalar(select(NewsletterRun).where(NewsletterRun.id == run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    return run


@runs_router.get("", response_model=RunListResponse)
def list_runs(
    request: Request,
    db: DbSession,
    newsletter_id: int | None = None,
    run_status: str | None = None,
    trigger_mode: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> RunListResponse:
    require_authenticated_user(request, db)
    statement = select(NewsletterRun).order_by(NewsletterRun.created_at.desc())
    if newsletter_id is not None:
        statement = statement.where(NewsletterRun.newsletter_id == newsletter_id)
    if run_status is not None:
        statement = statement.where(NewsletterRun.run_status == run_status)
    if trigger_mode is not None:
        statement = statement.where(NewsletterRun.trigger_mode == trigger_mode)
    if date_from is not None:
        start_of_day = datetime.combine(date_from, time.min, tzinfo=UTC)
        statement = statement.where(NewsletterRun.created_at >= start_of_day)
    if date_to is not None:
        # Use next-day start exclusive so the entire selected day is included
        end_of_day = datetime.combine(date_to, time.min, tzinfo=UTC)
        next_day = end_of_day + timedelta(days=1)
        statement = statement.where(NewsletterRun.created_at < next_day)

    runs = db.scalars(statement).all()
    return RunListResponse(items=[NewsletterRunSummary.model_validate(run) for run in runs])


@runs_router.get("/{run_id}", response_model=RunDetailResponse)
def get_run_detail(run_id: int, request: Request, db: DbSession) -> RunDetailResponse:
    require_authenticated_user(request, db)
    run = get_run_or_404(db, run_id)
    newsletter_snapshot = NewsletterSummary(
        id=run.newsletter_id,
        name=run.snapshot_newsletter_name or "",
        slug=run.snapshot_newsletter_slug or "",
        description=None,
        prompt=run.snapshot_prompt or "",
        draft_subject=run.snapshot_subject,
        draft_preheader=run.snapshot_preheader,
        draft_body_text=run.snapshot_body_text,
        provider_name=run.provider_name,
        model_name=run.model_name,
        template_key=run.template_key,
        audience_name="",
        delivery_topic=run.snapshot_delivery_topic or "",
        timezone="UTC",
        schedule_cron=None,
        schedule_enabled=False,
        status=run.snapshot_status_at_run or "",
        notes=None,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )
    return RunDetailResponse(
        run=NewsletterRunSummary.model_validate(run),
        newsletter=newsletter_snapshot,
        newsletter_snapshot=newsletter_snapshot,
        recipient_emails=json.loads(run.snapshot_recipient_emails or "[]"),
        recipient_outcomes=[
            RecipientSendOutcomeResponse(**outcome)
            for outcome in json.loads(run.delivery_outcomes or "[]")
        ],
        events=[NewsletterRunEventSummary.model_validate(event) for event in run.events],
    )


@runs_router.post("/{run_id}/reconcile", response_model=RunReconciliationResponse)
def reconcile_run_delivery(
    run_id: int,
    request: Request,
    db: DbSession,
) -> RunReconciliationResponse:
    require_authenticated_user(request, db)
    run = get_run_or_404(db, run_id)
    stored_outcomes = json.loads(run.delivery_outcomes or "[]")
    created_events: list[NewsletterRunEvent] = []
    for outcome in stored_outcomes:
        reconciliation = retrieve_email_status(
            settings=get_settings(),
            provider_id=outcome.get("provider_id"),
            current_mode=run.result_mode,
        )
        event = NewsletterRunEvent(
            run_id=run.id,
            event_type="reconciliation",
            event_status=reconciliation.event_status,
            message=reconciliation.message,
            provider_id=reconciliation.provider_id,
        )
        db.add(event)
        created_events.append(event)

    db.commit()
    for event in created_events:
        db.refresh(event)

    return RunReconciliationResponse(
        events=[NewsletterRunEventSummary.model_validate(event) for event in created_events]
    )
