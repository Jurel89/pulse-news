from __future__ import annotations

import json
import re
import secrets

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.ai_generation import generate_newsletter_draft
from app.auth import require_authenticated_user
from app.config import get_settings
from app.deps import DbSession
from app.email_delivery import send_test_email
from app.email_templates import render_newsletter
from app.models import AuditEvent, Newsletter, NewsletterRecipient
from app.schemas import (
    NewsletterCreateRequest,
    NewsletterDetail,
    NewsletterGenerationResponse,
    NewsletterPreviewResponse,
    NewsletterSummary,
    NewsletterTestSendRequest,
    NewsletterTestSendResponse,
    NewsletterUpdateRequest,
)

newsletters_router = APIRouter(prefix="/newsletters", tags=["newsletters"])


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


def get_newsletter_or_404(db: DbSession, newsletter_id: int) -> Newsletter:
    newsletter = db.scalar(select(Newsletter).where(Newsletter.id == newsletter_id))
    if newsletter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Newsletter not found.")
    return newsletter


def ensure_unique_slug(db: DbSession, *, desired_slug: str, current_id: int | None = None) -> str:
    slug = desired_slug
    suffix = 1
    while True:
        existing = db.scalar(select(Newsletter).where(Newsletter.slug == slug))
        if existing is None or existing.id == current_id:
            return slug
        suffix += 1
        slug = f"{desired_slug}-{suffix}"


def parse_recipient_import_text(recipient_import_text: str) -> list[str]:
    entries = re.split(r"[\n,;]+", recipient_import_text)
    normalized: list[str] = []
    for entry in entries:
        email = entry.strip().lower()
        if email and email not in normalized:
            normalized.append(email)
    return normalized


def replace_newsletter_recipients(newsletter: Newsletter, recipient_import_text: str) -> None:
    parsed_emails = parse_recipient_import_text(recipient_import_text)
    newsletter.recipients.clear()
    newsletter.recipients.extend(
        NewsletterRecipient(
            email=email,
            is_active=True,
            unsubscribe_token=secrets.token_urlsafe(16),
        )
        for email in parsed_emails
    )


def serialize_newsletter_detail(newsletter: Newsletter) -> NewsletterDetail:
    return NewsletterDetail(
        **NewsletterSummary.model_validate(newsletter).model_dump(),
        recipients=[
            {
                "id": recipient.id,
                "email": recipient.email,
                "is_active": recipient.is_active,
                "unsubscribe_token": recipient.unsubscribe_token,
            }
            for recipient in newsletter.recipients
        ],
        recipient_import_text="\n".join(recipient.email for recipient in newsletter.recipients),
    )


@newsletters_router.get("", response_model=list[NewsletterSummary])
def list_newsletters(request: Request, db: DbSession) -> list[NewsletterSummary]:
    require_authenticated_user(request, db)
    newsletters = db.scalars(select(Newsletter).order_by(Newsletter.updated_at.desc())).all()
    return [NewsletterSummary.model_validate(newsletter) for newsletter in newsletters]


@newsletters_router.post("", response_model=NewsletterDetail, status_code=status.HTTP_201_CREATED)
def create_newsletter(
    payload: NewsletterCreateRequest,
    request: Request,
    db: DbSession,
) -> NewsletterDetail:
    user = require_authenticated_user(request, db)
    newsletter = Newsletter(
        name=payload.name,
        slug=ensure_unique_slug(db, desired_slug=slugify(payload.name)),
        description=payload.description,
        prompt=payload.prompt,
        draft_subject=payload.draft_subject,
        draft_preheader=payload.draft_preheader,
        draft_body_text=payload.draft_body_text,
        provider_name=payload.provider_name,
        model_name=payload.model_name,
        template_key=payload.template_key,
        audience_name=payload.audience_name,
        timezone=payload.timezone,
        schedule_cron=payload.schedule_cron,
        status=payload.status,
        notes=payload.notes,
    )
    replace_newsletter_recipients(newsletter, payload.recipient_import_text)
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
    return serialize_newsletter_detail(newsletter)


@newsletters_router.get("/{newsletter_id}", response_model=NewsletterDetail)
def get_newsletter(newsletter_id: int, request: Request, db: DbSession) -> NewsletterDetail:
    require_authenticated_user(request, db)
    newsletter = get_newsletter_or_404(db, newsletter_id)
    return serialize_newsletter_detail(newsletter)


@newsletters_router.get("/{newsletter_id}/preview", response_model=NewsletterPreviewResponse)
def preview_newsletter(
    newsletter_id: int,
    request: Request,
    db: DbSession,
) -> NewsletterPreviewResponse:
    require_authenticated_user(request, db)
    newsletter = get_newsletter_or_404(db, newsletter_id)
    rendered = render_newsletter(newsletter)
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
    rendered = render_newsletter(newsletter)
    result = send_test_email(
        settings=get_settings(),
        rendered=rendered,
        to_email=payload.to_email,
    )
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
    newsletter.draft_subject = generated.subject
    newsletter.draft_preheader = generated.preheader
    newsletter.draft_body_text = generated.body_text
    db.add(newsletter)
    db.commit()
    db.refresh(newsletter)
    return NewsletterGenerationResponse(
        status=generated.status,
        mode=generated.mode,
        message=generated.message,
        newsletter=serialize_newsletter_detail(newsletter),
    )


@newsletters_router.put("/{newsletter_id}", response_model=NewsletterDetail)
def update_newsletter(
    newsletter_id: int,
    payload: NewsletterUpdateRequest,
    request: Request,
    db: DbSession,
) -> NewsletterDetail:
    user = require_authenticated_user(request, db)
    newsletter = get_newsletter_or_404(db, newsletter_id)

    newsletter.name = payload.name
    newsletter.slug = ensure_unique_slug(
        db,
        desired_slug=slugify(payload.name),
        current_id=newsletter.id,
    )
    newsletter.description = payload.description
    newsletter.prompt = payload.prompt
    newsletter.draft_subject = payload.draft_subject
    newsletter.draft_preheader = payload.draft_preheader
    newsletter.draft_body_text = payload.draft_body_text
    newsletter.provider_name = payload.provider_name
    newsletter.model_name = payload.model_name
    newsletter.template_key = payload.template_key
    newsletter.audience_name = payload.audience_name
    newsletter.timezone = payload.timezone
    newsletter.schedule_cron = payload.schedule_cron
    newsletter.status = payload.status
    newsletter.notes = payload.notes
    replace_newsletter_recipients(newsletter, payload.recipient_import_text)

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
    return serialize_newsletter_detail(newsletter)


@newsletters_router.post("/{newsletter_id}/archive", response_model=NewsletterDetail)
def archive_newsletter(newsletter_id: int, request: Request, db: DbSession) -> NewsletterDetail:
    user = require_authenticated_user(request, db)
    newsletter = get_newsletter_or_404(db, newsletter_id)
    newsletter.status = "archived"
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
    return serialize_newsletter_detail(newsletter)


@newsletters_router.delete("/{newsletter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_newsletter(newsletter_id: int, request: Request, db: DbSession) -> None:
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
    db.delete(newsletter)
    db.commit()
