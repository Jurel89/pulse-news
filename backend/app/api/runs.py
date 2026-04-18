from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import String, cast, func, or_, select

from app.auth import require_authenticated_user
from app.deps import DbSession
from app.models import NewsletterRun, NewsletterRunEvent
from app.schemas import (
    NewsletterRunEventSummary,
    NewsletterRunSummary,
    NewsletterSummary,
    OperationalEventListResponse,
    OperationalEventSummary,
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


def _normalize_filter_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _apply_date_filters(statement, column, date_from: date | None, date_to: date | None):
    if date_from is not None:
        start_of_day = datetime.combine(date_from, time.min, tzinfo=UTC)
        statement = statement.where(column >= start_of_day)
    if date_to is not None:
        end_of_day = datetime.combine(date_to, time.min, tzinfo=UTC)
        next_day = end_of_day + timedelta(days=1)
        statement = statement.where(column < next_day)
    return statement


def _build_newsletter_label(run: NewsletterRun) -> str:
    return (
        run.snapshot_newsletter_name
        or run.snapshot_newsletter_slug
        or f"Newsletter #{run.newsletter_id}"
    )


def _build_related_entity(run: NewsletterRun) -> str:
    return f"{_build_newsletter_label(run)} · Run #{run.id}"


def _build_run_message(run: NewsletterRun) -> str:
    if run.result_message:
        return run.result_message

    recipient_label = "recipient" if run.recipient_count == 1 else "recipients"
    trigger_label = run.trigger_mode.replace("-", " ")
    return (
        f"{trigger_label.capitalize()} run {run.run_status} "
        f"for {run.recipient_count} {recipient_label}."
    )


@runs_router.get("", response_model=RunListResponse)
def list_runs(
    request: Request,
    db: DbSession,
    newsletter_id: int | None = None,
    run_type: str | None = None,
    run_status: str | None = None,
    trigger_mode: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> RunListResponse:
    require_authenticated_user(request, db)
    statement = select(NewsletterRun).order_by(NewsletterRun.created_at.desc())
    if newsletter_id is not None:
        statement = statement.where(NewsletterRun.newsletter_id == newsletter_id)
    if run_type is not None:
        statement = statement.where(NewsletterRun.run_type == run_type)
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


@runs_router.get("/events", response_model=OperationalEventListResponse)
def list_run_operational_events(
    request: Request,
    db: DbSession,
    newsletter_id: int | None = None,
    event_type: str | None = None,
    status: str | None = None,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 100,
    include_runs: bool = False,
) -> OperationalEventListResponse:
    require_authenticated_user(request, db)

    normalized_event_type = _normalize_filter_value(event_type)
    normalized_status = _normalize_filter_value(status)
    normalized_search = _normalize_filter_value(search)
    normalized_limit = min(max(limit, 1), 200)

    include_run_events = True

    run_statement = select(NewsletterRun).order_by(NewsletterRun.created_at.desc())
    event_statement = (
        select(NewsletterRunEvent, NewsletterRun)
        .join(NewsletterRun, NewsletterRunEvent.run_id == NewsletterRun.id)
        .order_by(NewsletterRunEvent.created_at.desc())
    )

    if newsletter_id is not None:
        run_statement = run_statement.where(NewsletterRun.newsletter_id == newsletter_id)
        event_statement = event_statement.where(NewsletterRun.newsletter_id == newsletter_id)

    if normalized_status is not None:
        run_statement = run_statement.where(NewsletterRun.run_status == normalized_status)
        event_statement = event_statement.where(
            NewsletterRunEvent.event_status == normalized_status
        )

    if normalized_event_type is not None:
        if normalized_event_type.startswith("run-"):
            include_run_events = False
            include_runs = True
            run_statement = run_statement.where(
                NewsletterRun.trigger_mode == normalized_event_type.removeprefix("run-")
            )
        else:
            include_runs = False
            event_statement = event_statement.where(
                NewsletterRunEvent.event_type == normalized_event_type
            )

    if normalized_search is not None:
        pattern = f"%{normalized_search.lower()}%"
        identifier_pattern = f"%{normalized_search}%"
        run_statement = run_statement.where(
            or_(
                func.lower(NewsletterRun.trigger_mode).like(pattern),
                func.lower(NewsletterRun.run_status).like(pattern),
                func.lower(func.coalesce(NewsletterRun.result_message, "")).like(pattern),
                func.lower(func.coalesce(NewsletterRun.snapshot_newsletter_name, "")).like(pattern),
                func.lower(func.coalesce(NewsletterRun.snapshot_newsletter_slug, "")).like(pattern),
                cast(NewsletterRun.id, String).like(identifier_pattern),
            )
        )
        event_statement = event_statement.where(
            or_(
                func.lower(NewsletterRunEvent.event_type).like(pattern),
                func.lower(NewsletterRunEvent.event_status).like(pattern),
                func.lower(NewsletterRunEvent.message).like(pattern),
                func.lower(func.coalesce(NewsletterRunEvent.provider_id, "")).like(pattern),
                func.lower(NewsletterRun.trigger_mode).like(pattern),
                func.lower(func.coalesce(NewsletterRun.snapshot_newsletter_name, "")).like(pattern),
                func.lower(func.coalesce(NewsletterRun.snapshot_newsletter_slug, "")).like(pattern),
                cast(NewsletterRun.id, String).like(identifier_pattern),
            )
        )

    run_statement = _apply_date_filters(
        run_statement,
        NewsletterRun.created_at,
        date_from,
        date_to,
    )
    event_statement = _apply_date_filters(
        event_statement,
        NewsletterRunEvent.created_at,
        date_from,
        date_to,
    )

    runs = db.scalars(run_statement.limit(normalized_limit)).all() if include_runs else []
    run_event_rows = (
        db.execute(event_statement.limit(normalized_limit)).all() if include_run_events else []
    )

    items = [
        OperationalEventSummary(
            id=f"run-{run.id}",
            source="run",
            source_id=run.id,
            run_id=run.id,
            newsletter_id=run.newsletter_id,
            newsletter_name=run.snapshot_newsletter_name,
            newsletter_slug=run.snapshot_newsletter_slug,
            event_type=f"run-{run.trigger_mode}",
            status=run.run_status,
            message=_build_run_message(run),
            related_entity=_build_related_entity(run),
            trigger_mode=run.trigger_mode,
            recipient_count=run.recipient_count,
            created_at=run.created_at,
        )
        for run in runs
    ]

    items.extend(
        OperationalEventSummary(
            id=f"run-event-{run_event.id}",
            source="run_event",
            source_id=run_event.id,
            run_id=run.id,
            newsletter_id=run.newsletter_id,
            newsletter_name=run.snapshot_newsletter_name,
            newsletter_slug=run.snapshot_newsletter_slug,
            event_type=run_event.event_type,
            status=run_event.event_status,
            message=run_event.message,
            related_entity=_build_related_entity(run),
            trigger_mode=run.trigger_mode,
            recipient_count=run.recipient_count,
            provider_id=run_event.provider_id,
            created_at=run_event.created_at,
        )
        for run_event, run in run_event_rows
    )

    items.sort(key=lambda item: item.created_at, reverse=True)
    return OperationalEventListResponse(items=items[:normalized_limit])


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
        subject=run.rendered_subject or run.snapshot_subject,
        preheader=run.rendered_preheader or run.snapshot_preheader,
        body_text=run.rendered_plain_text or run.snapshot_body_text,
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
        newsletter_snapshot=newsletter_snapshot,
        recipient_emails=json.loads(run.snapshot_recipient_emails or "[]"),
        recipient_outcomes=[
            RecipientSendOutcomeResponse(**outcome)
            for outcome in json.loads(run.delivery_outcomes or "[]")
        ],
        events=[NewsletterRunEventSummary.model_validate(event) for event in run.events],
    )
