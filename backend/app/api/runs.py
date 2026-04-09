from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.auth import require_authenticated_user
from app.deps import DbSession
from app.models import NewsletterRun
from app.schemas import (
    NewsletterRunSummary,
    RecipientSendOutcomeResponse,
    RunDetailResponse,
    RunListResponse,
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
    date_from: datetime | None = None,
    date_to: datetime | None = None,
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
        statement = statement.where(NewsletterRun.created_at >= date_from)
    if date_to is not None:
        statement = statement.where(NewsletterRun.created_at <= date_to)

    runs = db.scalars(statement).all()
    return RunListResponse(items=[NewsletterRunSummary.model_validate(run) for run in runs])


@runs_router.get("/{run_id}", response_model=RunDetailResponse)
def get_run_detail(run_id: int, request: Request, db: DbSession) -> RunDetailResponse:
    require_authenticated_user(request, db)
    run = get_run_or_404(db, run_id)
    return RunDetailResponse(
        run=NewsletterRunSummary.model_validate(run),
        newsletter=run.newsletter,
        recipient_emails=json.loads(run.snapshot_recipient_emails or "[]"),
        recipient_outcomes=[
            RecipientSendOutcomeResponse(**outcome)
            for outcome in json.loads(run.delivery_outcomes or "[]")
        ],
    )
