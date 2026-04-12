from __future__ import annotations

import json
import re
from html import escape

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.auth import require_authenticated_user
from app.deps import DbSession
from app.models import AuditEvent, EmailTemplate, Newsletter
from app.schemas import (
    EmailTemplateCreateRequest,
    EmailTemplateDetail,
    EmailTemplatePreviewRequest,
    EmailTemplatePreviewResponse,
    EmailTemplateSummary,
    EmailTemplateUpdateRequest,
)

email_templates_router = APIRouter(prefix="/email-templates", tags=["email-templates"])

PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")
DEFAULT_PREVIEW_VARIABLES = {
    "subject": "Sample subject",
    "preheader": "Sample preheader text",
    "headline": "Pulse News Preview",
    "newsletter_name": "Pulse News",
    "body_html": "<p>This is a sample email template preview.</p>",
    "content": "<p>This is a sample email template preview.</p>",
}

TEMPLATE_PRESETS = [
    {
        "key": "minimal",
        "name": "Minimal",
        "description": "Clean, minimal layout with centered content",
        "html_template": """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{subject}}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
                Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header { text-align: center; margin-bottom: 30px; }
        .content { background: #fff; padding: 30px; }
        h1 { color: #111; font-size: 24px; margin-bottom: 20px; }
        .footer { text-align: center; margin-top: 30px; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{headline}}</h1>
    </div>
    <div class="content">
        {{body_html}}
    </div>
    <div class="footer">
        <p>{{newsletter_name}}</p>
    </div>
</body>
</html>""",
    },
    {
        "key": "newsletter",
        "name": "Newsletter",
        "description": "Classic newsletter layout with header and styled content blocks",
        "html_template": """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{subject}}</title>
    <style>
        body {
            font-family: Georgia, serif;
            line-height: 1.8;
            color: #222;
            background: #f5f5f5;
            margin: 0;
            padding: 20px;
        }
        .container { max-width: 600px; margin: 0 auto; background: #fff; }
        .header {
            background: #2c3e50;
            color: #fff;
            padding: 40px 30px;
            text-align: center;
        }
        .header h1 { margin: 0; font-size: 28px; font-weight: normal; }
        .preheader { color: #bdc3c7; font-size: 14px; margin-top: 10px; }
        .content { padding: 40px 30px; }
        .content h2 { color: #2c3e50; font-size: 22px; margin-top: 0; }
        .content p { margin-bottom: 20px; }
        .footer {
            background: #ecf0f1;
            padding: 20px 30px;
            text-align: center;
            font-size: 12px;
            color: #7f8c8d;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{headline}}</h1>
            <div class="preheader">{{preheader}}</div>
        </div>
        <div class="content">
            {{body_html}}
        </div>
        <div class="footer">
            <p>{{newsletter_name}}</p>
        </div>
    </div>
</body>
</html>""",
    },
    {
        "key": "modern",
        "name": "Modern Card",
        "description": "Modern card-based design with subtle shadows and rounded corners",
        "html_template": """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{subject}}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
                Roboto, sans-serif;
            line-height: 1.6;
            color: #2d3748;
            background: #f7fafc;
            margin: 0;
            padding: 40px 20px;
        }
        .container { max-width: 600px; margin: 0 auto; }
        .card {
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .card-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            padding: 40px 30px;
        }
        .card-header h1 { margin: 0; font-size: 26px; font-weight: 600; }
        .card-body { padding: 40px 30px; }
        .card-body h2 {
            color: #4a5568;
            font-size: 20px;
            margin-top: 0;
        }
        .card-footer {
            padding: 20px 30px;
            text-align: center;
            font-size: 12px;
            color: #a0aec0;
            border-top: 1px solid #e2e8f0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="card-header">
                <h1>{{headline}}</h1>
            </div>
            <div class="card-body">
                {{body_html}}
            </div>
            <div class="card-footer">
                {{newsletter_name}}
            </div>
        </div>
    </div>
</body>
</html>""",
    },
    {
        "key": "bulletin",
        "name": "Bulletin",
        "description": "Simple bulletin style with border accent and clean typography",
        "html_template": """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{subject}}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
                Roboto, sans-serif;
            line-height: 1.7;
            color: #333;
            background: #fff;
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            border-left: 4px solid #e74c3c;
        }
        .header { padding: 30px; border-bottom: 1px solid #eee; }
        .header h1 { margin: 0; font-size: 24px; color: #2c3e50; }
        .content { padding: 30px; }
        .content h2 { font-size: 20px; color: #34495e; margin-top: 0; }
        .footer {
            padding: 20px 30px;
            border-top: 1px solid #eee;
            font-size: 12px;
            color: #7f8c8d;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{headline}}</h1>
        </div>
        <div class="content">
            {{body_html}}
        </div>
        <div class="footer">
            {{newsletter_name}}
        </div>
    </div>
</body>
</html>""",
    },
]


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
        )
    )


def get_email_template_or_404(db: DbSession, email_template_id: int) -> EmailTemplate:
    email_template = db.scalar(select(EmailTemplate).where(EmailTemplate.id == email_template_id))
    if email_template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email template not found.",
        )
    return email_template


def ensure_unique_email_template_key(
    db: DbSession,
    *,
    key: str,
    current_id: int | None = None,
) -> None:
    existing = db.scalar(select(EmailTemplate).where(EmailTemplate.key == key))
    if existing is not None and existing.id != current_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email template key already exists.",
        )


def clear_default_email_templates(db: DbSession, *, exclude_id: int | None = None) -> None:
    statement = select(EmailTemplate).where(EmailTemplate.is_default.is_(True))
    if exclude_id is not None:
        statement = statement.where(EmailTemplate.id != exclude_id)
    for email_template in db.scalars(statement).all():
        email_template.is_default = False


def serialize_email_template_detail(email_template: EmailTemplate) -> EmailTemplateDetail:
    return EmailTemplateDetail(
        **EmailTemplateSummary.model_validate(email_template).model_dump(),
        html_template=email_template.html_template,
    )


def render_template_preview(html_template: str, variables: dict[str, str]) -> str:
    merged_variables = {**DEFAULT_PREVIEW_VARIABLES, **variables}

    def replace_placeholder(match: re.Match[str]) -> str:
        key = match.group(1)
        value = merged_variables.get(key, "")
        if key.endswith("_html") or key in {"content", "body", "html"}:
            return value
        return escape(value)

    return PLACEHOLDER_RE.sub(replace_placeholder, html_template)


@email_templates_router.get("", response_model=list[EmailTemplateSummary])
def list_email_templates(request: Request, db: DbSession) -> list[EmailTemplateSummary]:
    require_authenticated_user(request, db)
    email_templates = db.scalars(
        select(EmailTemplate).order_by(EmailTemplate.updated_at.desc())
    ).all()
    return [
        EmailTemplateSummary.model_validate(email_template) for email_template in email_templates
    ]


@email_templates_router.get("/presets/list")
def list_template_presets(request: Request, db: DbSession) -> list[dict]:
    require_authenticated_user(request, db)
    return TEMPLATE_PRESETS


@email_templates_router.post(
    "",
    response_model=EmailTemplateDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_email_template(
    payload: EmailTemplateCreateRequest,
    request: Request,
    db: DbSession,
) -> EmailTemplateDetail:
    user = require_authenticated_user(request, db)
    ensure_unique_email_template_key(db, key=payload.key)

    email_template = EmailTemplate(
        name=payload.name,
        key=payload.key,
        description=payload.description,
        html_template=payload.html_template,
        is_default=payload.is_default,
    )
    db.add(email_template)
    db.flush()

    if email_template.is_default:
        clear_default_email_templates(db, exclude_id=email_template.id)

    create_audit_event(
        db,
        actor_email=user.email,
        action="email_template.created",
        entity_type="email_template",
        entity_id=str(email_template.id),
        summary=f"Created email template {email_template.name}",
        payload={"key": email_template.key, "is_default": email_template.is_default},
    )
    db.commit()
    db.refresh(email_template)
    return serialize_email_template_detail(email_template)


@email_templates_router.get("/{email_template_id}", response_model=EmailTemplateDetail)
def get_email_template(
    email_template_id: int,
    request: Request,
    db: DbSession,
) -> EmailTemplateDetail:
    require_authenticated_user(request, db)
    email_template = get_email_template_or_404(db, email_template_id)
    return serialize_email_template_detail(email_template)


@email_templates_router.put("/{email_template_id}", response_model=EmailTemplateDetail)
def update_email_template(
    email_template_id: int,
    payload: EmailTemplateUpdateRequest,
    request: Request,
    db: DbSession,
) -> EmailTemplateDetail:
    user = require_authenticated_user(request, db)
    email_template = get_email_template_or_404(db, email_template_id)
    ensure_unique_email_template_key(db, key=payload.key, current_id=email_template.id)

    email_template.name = payload.name
    email_template.key = payload.key
    email_template.description = payload.description
    email_template.html_template = payload.html_template
    email_template.is_default = payload.is_default

    if email_template.is_default:
        clear_default_email_templates(db, exclude_id=email_template.id)

    db.add(email_template)
    create_audit_event(
        db,
        actor_email=user.email,
        action="email_template.updated",
        entity_type="email_template",
        entity_id=str(email_template.id),
        summary=f"Updated email template {email_template.name}",
        payload={"key": email_template.key, "is_default": email_template.is_default},
    )
    db.commit()
    db.refresh(email_template)
    return serialize_email_template_detail(email_template)


@email_templates_router.delete(
    "/{email_template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_email_template(
    email_template_id: int,
    request: Request,
    db: DbSession,
) -> Response:
    user = require_authenticated_user(request, db)
    email_template = get_email_template_or_404(db, email_template_id)
    if email_template.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System templates cannot be deleted.",
        )

    # Block deletion when in use by any newsletter (by template_id FK or template_key match)
    in_use_by_id = db.scalar(
        select(EmailTemplate)
        .join(EmailTemplate.newsletters)
        .where(EmailTemplate.id == email_template.id)
    )
    in_use_by_key = db.scalar(
        select(Newsletter).where(Newsletter.template_key == email_template.key)
    )
    if in_use_by_id or in_use_by_key:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a template that is referenced by newsletters. Reassign first.",
        )

    create_audit_event(
        db,
        actor_email=user.email,
        action="email_template.deleted",
        entity_type="email_template",
        entity_id=str(email_template.id),
        summary=f"Deleted email template {email_template.name}",
        payload={"key": email_template.key},
    )
    db.delete(email_template)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@email_templates_router.post(
    "/{email_template_id}/preview",
    response_model=EmailTemplatePreviewResponse,
)
def preview_email_template(
    email_template_id: int,
    request: Request,
    db: DbSession,
    payload: EmailTemplatePreviewRequest | None = None,
) -> EmailTemplatePreviewResponse:
    require_authenticated_user(request, db)
    email_template = get_email_template_or_404(db, email_template_id)
    return EmailTemplatePreviewResponse(
        html=render_template_preview(
            email_template.html_template,
            payload.variables if payload is not None else {},
        )
    )


@email_templates_router.post("/preview-live", response_model=EmailTemplatePreviewResponse)
def preview_live(
    request: Request,
    db: DbSession,
    payload: dict,
) -> EmailTemplatePreviewResponse:
    require_authenticated_user(request, db)
    html_template = payload.get("html_template", "")
    variables = payload.get("variables", {})
    return EmailTemplatePreviewResponse(html=render_template_preview(html_template, variables))


@email_templates_router.post(
    "/{email_template_id}/set-default",
    response_model=EmailTemplateDetail,
)
def set_default_email_template(
    email_template_id: int,
    request: Request,
    db: DbSession,
) -> EmailTemplateDetail:
    user = require_authenticated_user(request, db)
    email_template = get_email_template_or_404(db, email_template_id)

    clear_default_email_templates(db, exclude_id=email_template.id)
    email_template.is_default = True
    db.add(email_template)
    create_audit_event(
        db,
        actor_email=user.email,
        action="email_template.default_set",
        entity_type="email_template",
        entity_id=str(email_template.id),
        summary=f"Set email template {email_template.name} as default",
        payload={"key": email_template.key},
    )
    db.commit()
    db.refresh(email_template)
    return serialize_email_template_detail(email_template)
