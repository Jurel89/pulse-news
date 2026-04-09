from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str


class UserSummary(BaseModel):
    id: int
    email: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AuthActionResponse(BaseModel):
    message: str


class BootstrapRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class SessionResponse(BaseModel):
    initialized: bool
    authenticated: bool
    user: UserSummary | None = None


class NewsletterSummary(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None
    prompt: str
    draft_subject: str
    draft_preheader: str | None
    draft_body_text: str
    provider_name: str
    model_name: str
    template_key: str
    audience_name: str
    timezone: str
    schedule_cron: str | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NewsletterRecipientSummary(BaseModel):
    id: int
    email: str
    is_active: bool
    unsubscribe_token: str

    model_config = {"from_attributes": True}


class NewsletterCreateRequest(BaseModel):
    name: str
    description: str | None = None
    prompt: str = ""
    draft_subject: str = ""
    draft_preheader: str | None = None
    draft_body_text: str = ""
    provider_name: str = "openai"
    model_name: str = "gpt-4o-mini"
    template_key: str = "signal"
    audience_name: str = "default-audience"
    timezone: str = "UTC"
    schedule_cron: str | None = None
    status: str = "draft"
    notes: str | None = None
    recipient_import_text: str = ""


class NewsletterUpdateRequest(NewsletterCreateRequest):
    pass


class NewsletterDetail(NewsletterSummary):
    recipients: list[NewsletterRecipientSummary]
    recipient_import_text: str
