from __future__ import annotations

import hashlib
import json
import re
import secrets
import uuid
from zoneinfo import available_timezones

from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.ai_generation import generate_newsletter_content
from app.api.providers import get_provider_models
from app.auth import require_authenticated_user
from app.config import get_settings
from app.crypto import decrypt_secret
from app.deps import DbSession
from app.email_delivery import RecipientDeliveryTarget, send_newsletter_email
from app.email_templates import GenerationMeta, render_newsletter_content
from app.models import (
    ApiKey,
    AuditEvent,
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
    NewsletterJobUpdateRequest,
    NewsletterRunSummary,
    NewsletterSendResponse,
    NewsletterSummary,
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


def _summary_payload(newsletter: Newsletter) -> dict:
    return {
        "id": newsletter.id,
        "name": newsletter.name,
        "slug": newsletter.slug,
        "description": newsletter.description,
        "prompt": newsletter.prompt,
        "subject": newsletter.subject,
        "preheader": newsletter.preheader,
        "body_text": newsletter.body_text,
        "provider_id": newsletter.provider_id,
        "provider_name": newsletter.provider_name,
        "model_name": newsletter.model_name,
        "template_key": newsletter.template_key,
        "api_key_id": newsletter.api_key_id,
        "resend_api_key_id": newsletter.resend_api_key_id,
        "from_email": newsletter.from_email,
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Cannot send newsletter while status is '{newsletter.status}'.",
        )


def validate_schedule_allowed(newsletter: Newsletter) -> None:
    if newsletter.status not in SCHEDULE_ALLOWED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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


def _build_newsletter_attempt_key(
    *,
    newsletter_id: int,
    trigger_mode: str,
    recipient_emails: list[str],
    subject: str,
    preheader: str | None,
    body_text: str,
    fire_scope: str | None = None,
) -> str:
    normalized_recipients = ",".join(sorted(email.strip().lower() for email in recipient_emails))
    recipient_digest = hashlib.sha256(normalized_recipients.encode("utf-8")).hexdigest()[:16]
    snapshot = "\n".join((subject.strip(), (preheader or "").strip(), body_text.strip()))
    content_digest = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()[:16]
    scope = fire_scope or "default"
    return f"newsletter-{newsletter_id}-{trigger_mode}-{scope}-{content_digest}-{recipient_digest}"


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


def _newsletter_send_response_from_run(run: NewsletterRun) -> NewsletterSendResponse:
    try:
        recipient_outcomes = json.loads(run.delivery_outcomes or "[]")
    except json.JSONDecodeError:
        recipient_outcomes = []

    return NewsletterSendResponse(
        status=run.run_status,
        mode=run.result_mode or "unknown",
        message=run.result_message or "Returning existing run result.",
        run=NewsletterRunSummary.model_validate(run),
        recipient_outcomes=recipient_outcomes,
    )


def execute_newsletter_send(
    db: DbSession,
    newsletter: Newsletter,
    *,
    trigger_mode: str,
    idempotency_key: str | None = None,
    fire_scope: str | None = None,
    generation_meta: GenerationMeta | None = None,
) -> tuple[NewsletterSendResponse, NewsletterRun]:
    validate_send_allowed(newsletter)

    active_recipients = get_active_recipients(newsletter)
    active_recipient_emails = [recipient.email for recipient in active_recipients]
    if not active_recipient_emails:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Cannot send: no active recipients.",
        )

    attempt_key = idempotency_key or _build_newsletter_attempt_key(
        newsletter_id=newsletter.id,
        trigger_mode=trigger_mode,
        recipient_emails=active_recipient_emails,
        subject=newsletter.subject,
        preheader=newsletter.preheader,
        body_text=newsletter.body_text,
        fire_scope=fire_scope,
    )

    existing_run = db.scalar(select(NewsletterRun).where(NewsletterRun.attempt_key == attempt_key))
    if existing_run is not None:
        return _newsletter_send_response_from_run(existing_run), existing_run

    run = NewsletterRun(
        newsletter_id=newsletter.id,
        run_type="delivery",
        trigger_mode=trigger_mode,
        run_status="pending",
        provider_name=newsletter.provider_name,
        model_name=newsletter.model_name,
        template_key=newsletter.template_key,
        recipient_count=len(active_recipient_emails),
        snapshot_subject=newsletter.subject,
        snapshot_preheader=newsletter.preheader,
        snapshot_body_text=newsletter.body_text,
        snapshot_recipient_emails=json.dumps(active_recipient_emails),
        snapshot_prompt=newsletter.prompt,
        snapshot_newsletter_name=newsletter.name,
        snapshot_newsletter_slug=newsletter.slug,
        snapshot_delivery_topic=newsletter.delivery_topic,
        snapshot_status_at_run=newsletter.status,
        delivery_outcomes="[]",
        attempt_key=attempt_key,
    )
    db.add(run)
    db.flush()

    try:
        if not newsletter.body_text.strip():
            raise ValueError(
                "Newsletter has no content to send. Add body text or run generation before sending."
            )
        rendered = render_newsletter_content(
            newsletter,
            subject=newsletter.subject,
            preheader=newsletter.preheader,
            body=newsletter.body_text,
            generation_meta=generation_meta,
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
        subject="",
        preheader=None,
        body_text="",
        provider_id=payload.provider_id,
        provider_name=payload.provider_name,
        model_name=payload.model_name,
        template_key=payload.template_key,
        api_key_id=payload.api_key_id,
        resend_api_key_id=payload.resend_api_key_id,
        from_email=payload.from_email,
        audience_name=payload.audience_name,
        delivery_topic=payload.delivery_topic,
        timezone=payload.timezone,
        schedule_cron=payload.schedule_cron,
        schedule_enabled=payload.schedule_enabled,
        status=payload.status,
        notes=payload.notes,
    )
    upsert_newsletter_recipients(newsletter, payload.recipient_import_text)

    try:
        validate_schedule_configuration(newsletter)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
        {"key": "corporate", "name": "Corporate", "is_system": True},
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


BUILT_IN_TEMPLATE_KEYS = frozenset({"signal", "ledger", "corporate"})


def _ensure_template_exists(db: DbSession, template_key: str) -> None:
    if template_key in BUILT_IN_TEMPLATE_KEYS:
        return
    exists = db.scalar(select(EmailTemplate).where(EmailTemplate.key == template_key))
    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Provider does not exist.",
            )
        if not provider.is_enabled:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Provider is disabled.",
            )
        if provider.provider_type != payload.provider_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="API key is missing or inactive.",
            )
        if api_key.provider_type != payload.provider_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="API key provider_type does not match newsletter provider.",
            )

    resend_key: ApiKey | None = None
    if payload.resend_api_key_id is not None:
        resend_key = db.scalar(select(ApiKey).where(ApiKey.id == payload.resend_api_key_id))
        if resend_key is None or not resend_key.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Resend API key is missing or inactive.",
            )
        if resend_key.provider_type != "resend":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Resend API key must have provider_type 'resend'.",
            )

    _ensure_template_exists(db, payload.template_key)
    return provider, api_key, resend_key


@newsletters_router.get("/{newsletter_id}", response_model=NewsletterDetail)
def get_newsletter(newsletter_id: int, request: Request, db: DbSession) -> NewsletterDetail:
    require_authenticated_user(request, db)
    newsletter = get_newsletter_or_404(db, newsletter_id)
    return serialize_newsletter_detail(newsletter)


def _summarize_tool_loop_trace(trace_json: str | None) -> str | None:
    """Produce a one-line summary of the tool-loop trace for the logs page.

    Operators need to know at a glance whether web search actually fired or
    whether the provider silently ignored our tool payload. Format example:
      "Tool loop: 2 iterations; finish_reasons=tool_calls,stop; tool_calls=1,0"
    """
    if not trace_json:
        return None
    try:
        trace = json.loads(trace_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(trace, list) or not trace:
        return None
    finish_reasons = ",".join(
        str(entry.get("finish_reason") or "?") for entry in trace if isinstance(entry, dict)
    )
    tool_call_counts = ",".join(
        str(entry.get("tool_calls_count") or 0) for entry in trace if isinstance(entry, dict)
    )
    return (
        f"Tool loop: {len(trace)} iteration(s); "
        f"finish_reasons={finish_reasons}; tool_calls={tool_call_counts}"
    )


def _generation_meta_from_generated(newsletter: Newsletter, generated) -> GenerationMeta:
    """Build the render-time footer facts from what the backend observed on the
    generation call — never trust the model to self-report identity or cost."""
    input_tokens: int | None = None
    try:
        usage = json.loads(getattr(generated, "token_usage_json", None) or "{}")
        raw = usage.get("prompt_tokens") if isinstance(usage, dict) else None
        if isinstance(raw, int):
            input_tokens = raw
        elif isinstance(raw, str) and raw.isdigit():
            input_tokens = int(raw)
    except (json.JSONDecodeError, ValueError):
        input_tokens = None

    return GenerationMeta(
        provider=(newsletter.provider_name or None),
        model=(newsletter.model_name or None),
        input_tokens=input_tokens,
    )


def _create_generation_run(
    db: DbSession,
    newsletter: Newsletter,
    *,
    trigger_mode: str,
) -> NewsletterRun:
    active_recipient_emails = [recipient.email for recipient in get_active_recipients(newsletter)]
    run = NewsletterRun(
        newsletter_id=newsletter.id,
        run_type="generation",
        trigger_mode=trigger_mode,
        run_status="generating",
        provider_name=newsletter.provider_name,
        model_name=newsletter.model_name,
        template_key=newsletter.template_key,
        recipient_count=len(active_recipient_emails),
        snapshot_subject=newsletter.subject,
        snapshot_preheader=newsletter.preheader,
        snapshot_body_text=newsletter.body_text,
        snapshot_recipient_emails=json.dumps(active_recipient_emails),
        snapshot_prompt=newsletter.prompt,
        snapshot_newsletter_name=newsletter.name,
        snapshot_newsletter_slug=newsletter.slug,
        snapshot_delivery_topic=newsletter.delivery_topic,
        snapshot_status_at_run=newsletter.status,
        delivery_outcomes="[]",
        attempt_key=f"generation-{newsletter.id}-{uuid.uuid4()}",
        started_at=utc_now(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _mark_generation_failed(
    db: DbSession,
    run: NewsletterRun,
    *,
    message: str,
) -> None:
    run.run_status = "failed"
    run.failure_reason = message
    run.result_message = f"AI generation failed: {message}"
    run.completed_at = utc_now()
    db.add(run)
    add_run_event(
        db,
        run,
        event_type="generation",
        event_status="failed",
        message=message,
    )
    db.commit()


@newsletters_router.post("/{newsletter_id}/run", response_model=NewsletterSendResponse)
def run_newsletter(
    newsletter_id: int,
    request: Request,
    db: DbSession,
) -> NewsletterSendResponse:
    require_authenticated_user(request, db)
    newsletter = get_newsletter_or_404(db, newsletter_id)

    generation_run = _create_generation_run(db, newsletter, trigger_mode="manual-run")

    try:
        generated = generate_newsletter_content(newsletter, db_session=db)
    except Exception as exc:
        _mark_generation_failed(db, generation_run, message=f"{type(exc).__name__}: {exc}")
        raise

    if generated.status == "error":
        _mark_generation_failed(db, generation_run, message=generated.message)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Generation failed: {generated.message}",
        )

    tool_loop_summary = _summarize_tool_loop_trace(getattr(generated, "tool_loop_trace_json", None))
    generation_message = "AI generation succeeded."
    if tool_loop_summary:
        generation_message = f"{generation_message} {tool_loop_summary}"

    generation_run.run_status = "generated"
    generation_run.result_message = generation_message
    generation_run.completed_at = utc_now()
    db.add(generation_run)
    add_run_event(
        db,
        generation_run,
        event_type="generation",
        event_status="generated",
        message=generation_message,
    )

    newsletter.subject = generated.subject
    newsletter.preheader = generated.preheader
    newsletter.body_text = generated.body_text
    db.add(newsletter)

    if newsletter.api_key_id:
        api_key_obj = db.scalar(select(ApiKey).where(ApiKey.id == newsletter.api_key_id))
        if api_key_obj:
            api_key_obj.last_used_at = utc_now()

    db.commit()

    response, _run = execute_newsletter_send(
        db,
        newsletter,
        trigger_mode="manual-run",
        fire_scope=str(uuid.uuid4()),
        generation_meta=_generation_meta_from_generated(newsletter, generated),
    )
    return response


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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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


@newsletters_router.put("/{newsletter_id}", response_model=NewsletterDetail)
def update_newsletter(
    newsletter_id: int,
    payload: NewsletterJobUpdateRequest,
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
    newsletter.from_email = payload.from_email
    newsletter.audience_name = payload.audience_name
    newsletter.delivery_topic = payload.delivery_topic
    newsletter.timezone = payload.timezone
    newsletter.schedule_cron = payload.schedule_cron
    newsletter.schedule_enabled = payload.schedule_enabled
    newsletter.status = payload.status
    newsletter.notes = payload.notes

    upsert_newsletter_recipients(newsletter, payload.recipient_import_text)

    try:
        validate_schedule_configuration(newsletter)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
