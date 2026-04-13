from __future__ import annotations

import json
import re
import secrets
import uuid
from zoneinfo import available_timezones

from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.ai_generation import generate_newsletter_draft
from app.api.providers import get_provider_models
from app.auth import require_authenticated_user
from app.config import get_settings
from app.crypto import decrypt_secret
from app.deps import DbSession
from app.email_delivery import RecipientDeliveryTarget, send_newsletter_email, send_test_email
from app.email_templates import render_newsletter_content
from app.models import (
    ApiKey,
    AuditEvent,
    DraftRevision,
    EmailTemplate,
    Newsletter,
    NewsletterRecipient,
    NewsletterRun,
    NewsletterRunEvent,
    Provider,
    utc_now,
)
from app.schemas import (
    NewsletterCreateRequest,
    NewsletterDetail,
    NewsletterGenerationResponse,
    NewsletterPreviewResponse,
    NewsletterRunSummary,
    NewsletterSendResponse,
    NewsletterSummary,
    NewsletterTestSendRequest,
    NewsletterTestSendResponse,
    NewsletterUpdateRequest,
)

newsletters_router = APIRouter(prefix="/newsletters", tags=["newsletters"])

SEND_ALLOWED_STATUSES = {"active"}
SCHEDULE_ALLOWED_STATUSES = {"active"}


def mask_api_key(key_value: str) -> str:
    try:
        decrypted_key_value = decrypt_secret(key_value)
    except Exception:
        return "****"
    suffix = decrypted_key_value[-4:] if decrypted_key_value else ""
    return f"****{suffix}" if suffix else "****"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "newsletter"


def create_audit_event(
    db: DbSession,
    *,
    actor_email: str,
    action: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    payload: dict | None = None,
) -> None:
    db.add(
        AuditEvent(
            actor_email=actor_email,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            payload_json=json.dumps(payload) if payload else None,
        ),
    )


def get_active_recipient_emails(newsletter: Newsletter) -> list[str]:
    return [recipient.email for recipient in get_active_recipients(newsletter)]


def get_active_recipients(newsletter: Newsletter) -> list[NewsletterRecipient]:
    return [
        recipient
        for recipient in newsletter.recipients
        if recipient.is_active
        and recipient.unsubscribed_at is None
        and recipient.status == "subscribed"
    ]


def get_newsletter_or_404(db: DbSession, newsletter_id: int) -> Newsletter:
    newsletter = db.scalar(
        select(Newsletter).where(
            Newsletter.id == newsletter_id,
            Newsletter.deleted_at.is_(None),
        )
    )
    if newsletter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Newsletter not found.")
    return newsletter


def _next_revision_number(newsletter: Newsletter) -> int:
    if not newsletter.revisions:
        return 1
    return max(revision.version_number for revision in newsletter.revisions) + 1


def _create_revision(
    newsletter: Newsletter,
    *,
    state: str,
    origin: str,
    subject: str,
    preheader: str | None,
    body_text: str,
    prompt_snapshot: str | None,
    generation_run_id: int | None = None,
) -> DraftRevision:
    revision = DraftRevision(
        newsletter=newsletter,
        version_number=_next_revision_number(newsletter),
        state=state,
        origin=origin,
        subject=subject,
        preheader=preheader,
        body_text=body_text,
        prompt_snapshot=prompt_snapshot,
        generation_run_id=generation_run_id,
    )
    return revision


def _ensure_revision_projection(newsletter: Newsletter) -> DraftRevision | None:
    if newsletter.draft_head_revision is not None:
        return newsletter.draft_head_revision

    if newsletter.approved_revision is not None:
        newsletter.draft_head_revision = newsletter.approved_revision
        return newsletter.draft_head_revision

    if newsletter.revisions:
        sorted_revisions = sorted(
            newsletter.revisions, key=lambda revision: revision.version_number
        )
        newsletter.approved_revision = next(
            (revision for revision in reversed(sorted_revisions) if revision.state == "approved"),
            sorted_revisions[0],
        )
        newsletter.draft_head_revision = sorted_revisions[-1]
        return newsletter.draft_head_revision

    imported_revision = _create_revision(
        newsletter,
        state="approved",
        origin="imported",
        subject=newsletter.draft_subject,
        preheader=newsletter.draft_preheader,
        body_text=newsletter.draft_body_text,
        prompt_snapshot=newsletter.prompt,
    )
    newsletter.approved_revision = imported_revision
    newsletter.draft_head_revision = imported_revision
    return imported_revision


def _draft_revision(newsletter: Newsletter) -> DraftRevision | None:
    return _ensure_revision_projection(newsletter)


def _approved_revision(newsletter: Newsletter) -> DraftRevision | None:
    _ensure_revision_projection(newsletter)
    return newsletter.approved_revision


def _summary_payload(newsletter: Newsletter) -> dict:
    draft_revision = _draft_revision(newsletter)
    return {
        "id": newsletter.id,
        "name": newsletter.name,
        "slug": newsletter.slug,
        "description": newsletter.description,
        "prompt": newsletter.prompt,
        "draft_subject": draft_revision.subject if draft_revision else newsletter.draft_subject,
        "draft_preheader": draft_revision.preheader
        if draft_revision
        else newsletter.draft_preheader,
        "draft_body_text": draft_revision.body_text
        if draft_revision
        else newsletter.draft_body_text,
        "provider_id": newsletter.provider_id,
        "provider_name": newsletter.provider_name,
        "model_name": newsletter.model_name,
        "template_key": newsletter.template_key,
        "api_key_id": newsletter.api_key_id,
        "resend_api_key_id": newsletter.resend_api_key_id,
        "approved_revision_id": newsletter.approved_revision.id
        if newsletter.approved_revision
        else None,
        "draft_head_revision_id": draft_revision.id if draft_revision else None,
        "audience_name": newsletter.audience_name,
        "delivery_topic": newsletter.delivery_topic,
        "timezone": newsletter.timezone,
        "schedule_cron": newsletter.schedule_cron,
        "schedule_enabled": newsletter.schedule_enabled,
        "status": newsletter.status,
        "notes": newsletter.notes,
        "created_at": newsletter.created_at,
        "updated_at": newsletter.updated_at,
    }


def ensure_unique_slug(db: DbSession, *, desired_slug: str, current_id: int | None = None) -> str:
    slug = desired_slug
    suffix = 1
    while True:
        existing = db.scalar(select(Newsletter).where(Newsletter.slug == slug))
        if existing is None or existing.id == current_id:
            return slug
        suffix += 1
        slug = f"{desired_slug}-{suffix}"


EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def parse_recipient_import_text(recipient_import_text: str) -> list[str]:
    entries = re.split(r"[\n,;]+", recipient_import_text)
    normalized: list[str] = []
    invalid: list[str] = []
    for entry in entries:
        email = entry.strip().lower()
        if not email:
            continue
        if not EMAIL_RE.match(email):
            invalid.append(email)
            continue
        if email not in normalized:
            normalized.append(email)
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid email format: {', '.join(invalid[:5])}",
        )
    return normalized


def upsert_newsletter_recipients(newsletter: Newsletter, recipient_import_text: str) -> None:
    parsed_emails = parse_recipient_import_text(recipient_import_text)
    existing_by_email = {recipient.email: recipient for recipient in newsletter.recipients}
    parsed_email_set = set(parsed_emails)

    for email, recipient in existing_by_email.items():
        if email not in parsed_email_set and recipient.status == "subscribed":
            recipient.status = "removed_by_operator"
            recipient.is_active = False

    for email in parsed_emails:
        existing = existing_by_email.get(email)
        if existing is not None:
            if existing.status == "removed_by_operator":
                existing.status = "subscribed"
                existing.is_active = True
            continue
        newsletter.recipients.append(
            NewsletterRecipient(
                email=email,
                is_active=True,
                status="subscribed",
                unsubscribe_token=secrets.token_urlsafe(16),
            )
        )


def serialize_newsletter_detail(newsletter: Newsletter) -> NewsletterDetail:
    current_recipients = [
        recipient
        for recipient in newsletter.recipients
        if recipient.is_active
        and recipient.unsubscribed_at is None
        and recipient.status == "subscribed"
    ]
    return NewsletterDetail(
        **_summary_payload(newsletter),
        recipients=[
            {
                "id": recipient.id,
                "email": recipient.email,
                "is_active": recipient.is_active,
                "unsubscribe_token": recipient.unsubscribe_token,
                "unsubscribed_at": recipient.unsubscribed_at,
                "suppression_reason": recipient.suppression_reason,
            }
            for recipient in current_recipients
        ],
        recipient_import_text="\n".join(recipient.email for recipient in current_recipients),
    )


def validate_send_allowed(newsletter: Newsletter) -> None:
    if newsletter.status not in SEND_ALLOWED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot send newsletter while status is '{newsletter.status}'.",
        )


def validate_schedule_allowed(newsletter: Newsletter) -> None:
    if newsletter.status not in SCHEDULE_ALLOWED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot schedule newsletter in '{newsletter.status}' status.",
        )


def validate_schedule_configuration(newsletter: Newsletter) -> None:
    schedule_cron = " ".join((newsletter.schedule_cron or "").split())
    timezone = (newsletter.timezone or "UTC").strip() or "UTC"

    if newsletter.schedule_enabled and not schedule_cron:
        raise ValueError("schedule_cron is required when scheduling is enabled.")
    if not schedule_cron:
        return

    CronTrigger.from_crontab(schedule_cron, timezone=timezone)


def create_newsletter_run(
    newsletter: Newsletter,
    revision: DraftRevision,
    *,
    run_type: str,
    trigger_mode: str,
    run_status: str,
    result_mode: str | None = None,
    result_message: str | None = None,
    recipient_emails: list[str] | None = None,
) -> NewsletterRun:
    snapshot_recipient_emails = recipient_emails or get_active_recipient_emails(newsletter)
    return NewsletterRun(
        newsletter_id=newsletter.id,
        revision_id=revision.id,
        run_type=run_type,
        trigger_mode=trigger_mode,
        run_status=run_status,
        provider_name=newsletter.provider_name,
        model_name=newsletter.model_name,
        template_key=newsletter.template_key,
        recipient_count=len(snapshot_recipient_emails),
        snapshot_subject=revision.subject,
        snapshot_preheader=revision.preheader,
        snapshot_body_text=revision.body_text,
        snapshot_recipient_emails=json.dumps(snapshot_recipient_emails),
        delivery_outcomes="[]",
        result_mode=result_mode,
        result_message=result_message,
        snapshot_prompt=newsletter.prompt,
        snapshot_newsletter_name=newsletter.name,
        snapshot_newsletter_slug=newsletter.slug,
        snapshot_delivery_topic=newsletter.delivery_topic,
        snapshot_status_at_run=newsletter.status,
    )


def add_run_event(
    db: DbSession,
    run: NewsletterRun,
    *,
    event_type: str,
    event_status: str,
    message: str,
    provider_id: str | None = None,
) -> None:
    db.add(
        NewsletterRunEvent(
            run_id=run.id,
            event_type=event_type,
            event_status=event_status,
            message=message,
            provider_id=provider_id,
        )
    )


def execute_newsletter_send(
    db: DbSession,
    newsletter: Newsletter,
    *,
    revision: DraftRevision | None = None,
    trigger_mode: str,
) -> tuple[NewsletterSendResponse, NewsletterRun]:
    validate_send_allowed(newsletter)
    resolved_revision = revision or _approved_revision(newsletter)
    if resolved_revision is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot send newsletter without an approved revision.",
        )

    active_recipients = get_active_recipients(newsletter)
    active_recipient_emails = [recipient.email for recipient in active_recipients]
    if not active_recipient_emails:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot send: no active recipients.",
        )

    run = NewsletterRun(
        newsletter_id=newsletter.id,
        revision_id=resolved_revision.id,
        run_type="delivery",
        trigger_mode=trigger_mode,
        run_status="pending",
        provider_name=newsletter.provider_name,
        model_name=newsletter.model_name,
        template_key=newsletter.template_key,
        recipient_count=len(active_recipient_emails),
        snapshot_subject=resolved_revision.subject,
        snapshot_preheader=resolved_revision.preheader,
        snapshot_body_text=resolved_revision.body_text,
        snapshot_recipient_emails=json.dumps(active_recipient_emails),
        snapshot_prompt=newsletter.prompt,
        snapshot_newsletter_name=newsletter.name,
        snapshot_newsletter_slug=newsletter.slug,
        snapshot_delivery_topic=newsletter.delivery_topic,
        snapshot_status_at_run=newsletter.status,
        delivery_outcomes="[]",
        attempt_key=str(uuid.uuid4()),
    )
    db.add(run)
    db.flush()

    try:
        if not resolved_revision.body_text.strip():
            raise ValueError(
                "Newsletter has no content to send. "
                "Add body text or generate a draft before sending."
            )
        rendered = render_newsletter_content(
            newsletter,
            subject=resolved_revision.subject,
            preheader=resolved_revision.preheader,
            body=resolved_revision.body_text,
        )
        run.rendered_subject = rendered.subject
        run.rendered_preheader = rendered.preheader
        run.rendered_html = rendered.html
        run.rendered_plain_text = rendered.plain_text
        run.started_at = utc_now()
        run.run_status = "sending"
        db.flush()
        db.commit()
    except Exception as exc:
        run.run_status = "failed"
        run.failure_reason = str(exc)
        run.result_message = f"Failed to render newsletter: {exc}"
        run.completed_at = utc_now()
        db.flush()
        db.commit()
        raise

    try:
        result = send_newsletter_email(
            settings=get_settings(),
            rendered=rendered,
            recipient_targets=[
                RecipientDeliveryTarget(
                    email=recipient.email,
                    unsubscribe_token=recipient.unsubscribe_token,
                )
                for recipient in active_recipients
            ],
            attempt_key=run.attempt_key,
            newsletter=newsletter,
            db_session=db,
        )
    except Exception as exc:
        run.run_status = "failed"
        run.failure_reason = str(exc)
        run.result_message = f"Failed to send newsletter: {exc}"
        run.completed_at = utc_now()
        db.flush()
        db.commit()
        raise

    recipient_outcomes = [
        {
            "email": outcome.email,
            "status": outcome.status,
            "provider_id": outcome.provider_id,
            "detail": outcome.detail,
        }
        for outcome in result.recipient_outcomes
    ]
    run.run_status = result.status
    run.result_mode = result.mode
    run.result_message = result.message
    run.delivery_outcomes = json.dumps(recipient_outcomes)
    run.completed_at = utc_now()
    db.flush()

    for outcome in result.recipient_outcomes:
        add_run_event(
            db,
            run,
            event_type="delivery",
            event_status=outcome.status,
            message=outcome.detail,
            provider_id=outcome.provider_id,
        )
    db.commit()
    db.refresh(run)
    return (
        NewsletterSendResponse(
            status=result.status,
            mode=result.mode,
            message=result.message,
            run=NewsletterRunSummary.model_validate(run),
            recipient_outcomes=recipient_outcomes,
        ),
        run,
    )


@newsletters_router.get("", response_model=list[NewsletterSummary])
def list_newsletters(request: Request, db: DbSession) -> list[NewsletterSummary]:
    require_authenticated_user(request, db)
    newsletters = db.scalars(
        select(Newsletter)
        .where(Newsletter.deleted_at.is_(None))
        .order_by(Newsletter.updated_at.desc())
    ).all()
    for newsletter in newsletters:
        _ensure_revision_projection(newsletter)
    db.flush()
    return [
        NewsletterSummary.model_validate(_summary_payload(newsletter)) for newsletter in newsletters
    ]


@newsletters_router.post("", response_model=NewsletterDetail, status_code=status.HTTP_201_CREATED)
def create_newsletter(
    payload: NewsletterCreateRequest,
    request: Request,
    db: DbSession,
) -> NewsletterDetail:
    user = require_authenticated_user(request, db)
    _validate_newsletter_entities(db, payload)
    newsletter = Newsletter(
        name=payload.name,
        slug=ensure_unique_slug(db, desired_slug=slugify(payload.name)),
        description=payload.description,
        prompt=payload.prompt,
        draft_subject=payload.draft_subject,
        draft_preheader=payload.draft_preheader,
        draft_body_text=payload.draft_body_text,
        provider_id=payload.provider_id,
        provider_name=payload.provider_name,
        model_name=payload.model_name,
        template_key=payload.template_key,
        api_key_id=payload.api_key_id,
        resend_api_key_id=payload.resend_api_key_id,
        audience_name=payload.audience_name,
        delivery_topic=payload.delivery_topic,
        timezone=payload.timezone,
        schedule_cron=payload.schedule_cron,
        schedule_enabled=payload.schedule_enabled,
        status=payload.status,
        notes=payload.notes,
    )
    initial_revision = _create_revision(
        newsletter,
        state="approved",
        origin="imported",
        subject=payload.draft_subject,
        preheader=payload.draft_preheader,
        body_text=payload.draft_body_text,
        prompt_snapshot=payload.prompt,
    )
    newsletter.approved_revision = initial_revision
    newsletter.draft_head_revision = initial_revision
    upsert_newsletter_recipients(newsletter, payload.recipient_import_text)

    try:
        validate_schedule_configuration(newsletter)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid schedule configuration: {exc}",
        ) from exc

    db.add(newsletter)
    db.flush()
    create_audit_event(
        db,
        actor_email=user.email,
        action="newsletter.created",
        entity_type="newsletter",
        entity_id=str(newsletter.id),
        summary=f"Created newsletter {newsletter.name}",
        payload={"slug": newsletter.slug},
    )
    db.commit()
    db.refresh(newsletter)
    from app.scheduler import sync_newsletter_schedule

    sync_newsletter_schedule(newsletter)
    return serialize_newsletter_detail(newsletter)


@newsletters_router.get("/form-options")
def get_form_options(request: Request, db: DbSession) -> dict:
    require_authenticated_user(request, db)

    # Get all templates (both system and custom)
    all_templates = db.scalars(select(EmailTemplate).order_by(EmailTemplate.name)).all()
    template_options = [
        {"key": t.key, "name": t.name, "is_system": t.is_system} for t in all_templates
    ]

    built_in_templates = [
        {"key": "signal", "name": "Signal", "is_system": True},
        {"key": "ledger", "name": "Ledger", "is_system": True},
    ]

    existing_keys = {t["key"] for t in template_options}
    for built_in in built_in_templates:
        if built_in["key"] not in existing_keys:
            template_options.append(built_in)

    # Get configured providers
    providers = db.scalars(
        select(Provider).where(Provider.is_enabled.is_(True)).order_by(Provider.name)
    ).all()
    provider_options = [
        {
            "id": p.id,
            "name": p.name,
            "provider_type": p.provider_type,
            "default_model": p.default_model,
        }
        for p in providers
    ]

    models: dict[str, list[str]] = {}
    for provider in providers:
        provider_models = get_provider_models(provider, db=db)
        if provider_models:
            models[str(provider.id)] = provider_models

    # Get active API keys
    api_keys = db.scalars(
        select(ApiKey).where(ApiKey.is_active.is_(True)).order_by(ApiKey.name)
    ).all()
    api_key_options = [
        {
            "id": k.id,
            "name": k.name,
            "provider_type": k.provider_type,
            "masked_key": mask_api_key(k.key_value),
            "from_email": k.from_email,
        }
        for k in api_keys
    ]

    return {
        "templates": template_options,
        "providers": provider_options,
        "models": models,
        "api_keys": api_key_options,
        "timezones": sorted(available_timezones()),
    }


def _ensure_template_exists(db: DbSession, template_key: str) -> None:
    if template_key in {"signal", "ledger"}:
        return
    exists = db.scalar(select(EmailTemplate).where(EmailTemplate.key == template_key))
    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Template '{template_key}' does not exist.",
        )


def _get_active_api_key_for_provider(db: DbSession, provider_type: str) -> ApiKey | None:
    return db.scalar(
        select(ApiKey).where(
            ApiKey.provider_type == provider_type,
            ApiKey.is_active.is_(True),
        )
    )


def _validate_newsletter_entities(
    db: DbSession, payload: NewsletterCreateRequest
) -> tuple[Provider | None, ApiKey | None, ApiKey | None]:
    provider: Provider | None = None
    if payload.provider_id is not None:
        provider = db.scalar(select(Provider).where(Provider.id == payload.provider_id))
        if provider is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Provider does not exist.",
            )
        if not provider.is_enabled:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Provider is disabled.",
            )
        if provider.provider_type != payload.provider_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="provider_name does not match provider type.",
            )

        active_key = _get_active_api_key_for_provider(db, provider.provider_type)
        if active_key is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Provider '{provider.name}' has no active API key configured. "
                    f"Create an API key for provider type "
                    f"'{provider.provider_type}' first."
                ),
            )

    elif payload.provider_name:
        provider = db.scalar(
            select(Provider).where(
                Provider.provider_type == payload.provider_name,
                Provider.is_enabled.is_(True),
            )
        )
        if provider is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"No enabled provider found for type "
                    f"'{payload.provider_name}'. Create and enable a provider first."
                ),
            )

        active_key = _get_active_api_key_for_provider(db, provider.provider_type)
        if active_key is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Provider '{provider.name}' has no active API key configured. "
                    f"Create an API key for provider type "
                    f"'{provider.provider_type}' first."
                ),
            )

    api_key: ApiKey | None = None
    if payload.api_key_id is not None:
        api_key = db.scalar(select(ApiKey).where(ApiKey.id == payload.api_key_id))
        if api_key is None or not api_key.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="API key is missing or inactive.",
            )
        if api_key.provider_type != payload.provider_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="API key provider_type does not match newsletter provider.",
            )

    resend_key: ApiKey | None = None
    if payload.resend_api_key_id is not None:
        resend_key = db.scalar(select(ApiKey).where(ApiKey.id == payload.resend_api_key_id))
        if resend_key is None or not resend_key.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Resend API key is missing or inactive.",
            )
        if resend_key.provider_type != "resend":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Resend API key must have provider_type 'resend'.",
            )

    _ensure_template_exists(db, payload.template_key)
    return provider, api_key, resend_key


@newsletters_router.get("/{newsletter_id}", response_model=NewsletterDetail)
def get_newsletter(newsletter_id: int, request: Request, db: DbSession) -> NewsletterDetail:
    require_authenticated_user(request, db)
    newsletter = get_newsletter_or_404(db, newsletter_id)
    _ensure_revision_projection(newsletter)
    db.flush()
    return serialize_newsletter_detail(newsletter)


@newsletters_router.get("/{newsletter_id}/preview", response_model=NewsletterPreviewResponse)
def preview_newsletter(
    newsletter_id: int,
    request: Request,
    db: DbSession,
) -> NewsletterPreviewResponse:
    require_authenticated_user(request, db)
    newsletter = get_newsletter_or_404(db, newsletter_id)
    revision = _draft_revision(newsletter)
    if revision is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No draft revision found."
        )
    rendered = render_newsletter_content(
        newsletter,
        subject=revision.subject,
        preheader=revision.preheader,
        body=revision.body_text,
    )
    return NewsletterPreviewResponse(
        subject=rendered.subject,
        preheader=rendered.preheader,
        html=rendered.html,
        plain_text=rendered.plain_text,
        template_key=rendered.template_key,
    )


@newsletters_router.post("/{newsletter_id}/test-send", response_model=NewsletterTestSendResponse)
def test_send_newsletter(
    newsletter_id: int,
    payload: NewsletterTestSendRequest,
    request: Request,
    db: DbSession,
) -> NewsletterTestSendResponse:
    require_authenticated_user(request, db)
    newsletter = get_newsletter_or_404(db, newsletter_id)
    revision = _draft_revision(newsletter)
    if revision is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No draft revision found."
        )
    rendered = render_newsletter_content(
        newsletter,
        subject=revision.subject,
        preheader=revision.preheader,
        body=revision.body_text,
    )

    run = create_newsletter_run(
        newsletter,
        revision,
        run_type="test_send",
        trigger_mode="test-send",
        run_status="sending",
        recipient_emails=[payload.to_email],
    )
    db.add(run)
    db.flush()

    try:
        result = send_test_email(
            settings=get_settings(),
            rendered=rendered,
            to_email=payload.to_email,
            newsletter=newsletter,
            db_session=db,
        )
    except RuntimeError as exc:
        run.run_status = "failed"
        run.result_mode = "resend"
        run.result_message = str(exc)
        run.completed_at = utc_now()
        add_run_event(
            db,
            run,
            event_type="delivery",
            event_status="failed",
            message=str(exc),
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    run.run_status = result.status
    run.result_mode = result.mode
    run.result_message = result.message
    run.completed_at = utc_now()
    add_run_event(
        db,
        run,
        event_type="delivery",
        event_status=result.status,
        message=result.message,
        provider_id=result.provider_id,
    )
    db.commit()

    return NewsletterTestSendResponse(
        status=result.status,
        mode=result.mode,
        message=result.message,
        provider_id=result.provider_id,
        to_email=result.to_email,
    )


@newsletters_router.post(
    "/{newsletter_id}/generate-draft",
    response_model=NewsletterGenerationResponse,
)
def generate_draft(
    newsletter_id: int,
    request: Request,
    db: DbSession,
) -> NewsletterGenerationResponse:
    require_authenticated_user(request, db)
    newsletter = get_newsletter_or_404(db, newsletter_id)
    generated = generate_newsletter_draft(newsletter)
    revision = _create_revision(
        newsletter,
        state="candidate",
        origin="llm" if generated.status in {"generated", "fallback"} else "manual",
        subject=generated.subject,
        preheader=generated.preheader,
        body_text=generated.body_text,
        prompt_snapshot=newsletter.prompt,
    )
    newsletter.draft_head_revision = revision
    run = create_newsletter_run(
        newsletter,
        revision,
        run_type="generation",
        trigger_mode="manual-generate",
        run_status=generated.status,
        result_mode=generated.mode,
        result_message=generated.message,
    )
    db.add(newsletter)
    db.add(revision)
    db.add(run)
    db.flush()
    revision.generation_run_id = run.id
    add_run_event(
        db,
        run,
        event_type="generation",
        event_status=generated.status,
        message=generated.message,
    )

    if generated.status in {"ok", "fallback", "generated"} and newsletter.api_key_id:
        api_key_obj = db.scalar(select(ApiKey).where(ApiKey.id == newsletter.api_key_id))
        if api_key_obj:
            api_key_obj.last_used_at = utc_now()

    db.commit()
    db.refresh(newsletter)
    db.refresh(run)
    return NewsletterGenerationResponse(
        status=generated.status,
        mode=generated.mode,
        message=generated.message,
        revision_id=revision.id,
        newsletter=serialize_newsletter_detail(newsletter),
        run=NewsletterRunSummary.model_validate(run),
    )


@newsletters_router.post("/{newsletter_id}/schedule/resume", response_model=NewsletterDetail)
def resume_newsletter_schedule(
    newsletter_id: int,
    request: Request,
    db: DbSession,
) -> NewsletterDetail:
    require_authenticated_user(request, db)
    newsletter = get_newsletter_or_404(db, newsletter_id)

    if not (newsletter.schedule_cron or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot resume schedule without a cron expression.",
        )

    validate_schedule_allowed(newsletter)

    newsletter.schedule_cron = " ".join(newsletter.schedule_cron.split())
    newsletter.schedule_enabled = True

    try:
        validate_schedule_configuration(newsletter)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid schedule configuration: {exc}",
        ) from exc

    db.add(newsletter)
    db.commit()
    db.refresh(newsletter)
    from app.scheduler import sync_newsletter_schedule

    sync_newsletter_schedule(newsletter)
    return serialize_newsletter_detail(newsletter)


@newsletters_router.post("/{newsletter_id}/schedule/pause", response_model=NewsletterDetail)
def pause_newsletter_schedule(
    newsletter_id: int,
    request: Request,
    db: DbSession,
) -> NewsletterDetail:
    require_authenticated_user(request, db)
    newsletter = get_newsletter_or_404(db, newsletter_id)
    newsletter.schedule_enabled = False
    db.add(newsletter)
    db.commit()
    db.refresh(newsletter)
    from app.scheduler import sync_newsletter_schedule

    sync_newsletter_schedule(newsletter)
    return serialize_newsletter_detail(newsletter)


@newsletters_router.post("/{newsletter_id}/send", response_model=NewsletterSendResponse)
def send_newsletter(
    newsletter_id: int,
    request: Request,
    db: DbSession,
) -> NewsletterSendResponse:
    require_authenticated_user(request, db)
    newsletter = get_newsletter_or_404(db, newsletter_id)
    response, _run = execute_newsletter_send(
        db,
        newsletter,
        revision=_approved_revision(newsletter),
        trigger_mode="manual-send",
    )
    return response


@newsletters_router.put("/{newsletter_id}", response_model=NewsletterDetail)
def update_newsletter(
    newsletter_id: int,
    payload: NewsletterUpdateRequest,
    request: Request,
    db: DbSession,
) -> NewsletterDetail:
    user = require_authenticated_user(request, db)
    newsletter = get_newsletter_or_404(db, newsletter_id)
    _validate_newsletter_entities(db, payload)

    newsletter.name = payload.name
    newsletter.slug = ensure_unique_slug(
        db,
        desired_slug=slugify(payload.name),
        current_id=newsletter.id,
    )
    newsletter.description = payload.description
    newsletter.prompt = payload.prompt
    newsletter.provider_id = payload.provider_id
    newsletter.provider_name = payload.provider_name
    newsletter.model_name = payload.model_name
    newsletter.template_key = payload.template_key
    newsletter.api_key_id = payload.api_key_id
    newsletter.resend_api_key_id = payload.resend_api_key_id
    newsletter.audience_name = payload.audience_name
    newsletter.delivery_topic = payload.delivery_topic
    newsletter.timezone = payload.timezone
    newsletter.schedule_cron = payload.schedule_cron
    newsletter.schedule_enabled = payload.schedule_enabled
    newsletter.status = payload.status
    newsletter.notes = payload.notes

    draft_revision = _draft_revision(newsletter)
    approved_revision = _approved_revision(newsletter)
    if draft_revision is None:
        draft_revision = _create_revision(
            newsletter,
            state="candidate",
            origin="manual",
            subject=payload.draft_subject,
            preheader=payload.draft_preheader,
            body_text=payload.draft_body_text,
            prompt_snapshot=payload.prompt,
        )
        newsletter.draft_head_revision = draft_revision
    elif draft_revision.id == (approved_revision.id if approved_revision else None) and (
        draft_revision.subject != payload.draft_subject
        or draft_revision.preheader != payload.draft_preheader
        or draft_revision.body_text != payload.draft_body_text
    ):
        draft_revision = _create_revision(
            newsletter,
            state="candidate",
            origin="manual",
            subject=payload.draft_subject,
            preheader=payload.draft_preheader,
            body_text=payload.draft_body_text,
            prompt_snapshot=payload.prompt,
        )
        newsletter.draft_head_revision = draft_revision
    else:
        draft_revision.subject = payload.draft_subject
        draft_revision.preheader = payload.draft_preheader
        draft_revision.body_text = payload.draft_body_text
        draft_revision.prompt_snapshot = payload.prompt
        draft_revision.state = "candidate"

    upsert_newsletter_recipients(newsletter, payload.recipient_import_text)

    try:
        validate_schedule_configuration(newsletter)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid schedule configuration: {exc}",
        ) from exc

    db.add(newsletter)
    create_audit_event(
        db,
        actor_email=user.email,
        action="newsletter.updated",
        entity_type="newsletter",
        entity_id=str(newsletter.id),
        summary=f"Updated newsletter {newsletter.name}",
    )
    db.commit()
    db.refresh(newsletter)
    from app.scheduler import sync_newsletter_schedule

    sync_newsletter_schedule(newsletter)
    return serialize_newsletter_detail(newsletter)


@newsletters_router.post("/{newsletter_id}/pause", response_model=NewsletterDetail)
def pause_newsletter(newsletter_id: int, request: Request, db: DbSession) -> NewsletterDetail:
    user = require_authenticated_user(request, db)
    newsletter = get_newsletter_or_404(db, newsletter_id)
    newsletter.status = "paused"
    newsletter.schedule_enabled = False
    db.add(newsletter)
    create_audit_event(
        db,
        actor_email=user.email,
        action="newsletter.paused",
        entity_type="newsletter",
        entity_id=str(newsletter.id),
        summary=f"Paused newsletter {newsletter.name}",
    )
    db.commit()
    db.refresh(newsletter)
    from app.scheduler import sync_newsletter_schedule

    sync_newsletter_schedule(newsletter)
    return serialize_newsletter_detail(newsletter)


@newsletters_router.post("/{newsletter_id}/archive", response_model=NewsletterDetail)
def archive_newsletter(newsletter_id: int, request: Request, db: DbSession) -> NewsletterDetail:
    user = require_authenticated_user(request, db)
    newsletter = get_newsletter_or_404(db, newsletter_id)
    newsletter.status = "archived"
    newsletter.schedule_enabled = False
    db.add(newsletter)
    create_audit_event(
        db,
        actor_email=user.email,
        action="newsletter.archived",
        entity_type="newsletter",
        entity_id=str(newsletter.id),
        summary=f"Archived newsletter {newsletter.name}",
    )
    db.commit()
    db.refresh(newsletter)
    from app.scheduler import sync_newsletter_schedule

    sync_newsletter_schedule(newsletter)
    return serialize_newsletter_detail(newsletter)


@newsletters_router.delete(
    "/{newsletter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_newsletter(newsletter_id: int, request: Request, db: DbSession) -> Response:
    user = require_authenticated_user(request, db)
    newsletter = get_newsletter_or_404(db, newsletter_id)
    create_audit_event(
        db,
        actor_email=user.email,
        action="newsletter.deleted",
        entity_type="newsletter",
        entity_id=str(newsletter.id),
        summary=f"Deleted newsletter {newsletter.name}",
        payload={"slug": newsletter.slug},
    )
    newsletter.deleted_at = utc_now()
    newsletter.schedule_enabled = False
    db.add(newsletter)
    db.commit()
    from app.scheduler import sync_newsletter_schedule

    sync_newsletter_schedule(newsletter)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
