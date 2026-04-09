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
    schedule_enabled: bool
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
    unsubscribed_at: datetime | None = None
    suppression_reason: str | None = None

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
    delivery_topic: str = "default-topic"
    timezone: str = "UTC"
    schedule_cron: str | None = None
    schedule_enabled: bool = False
    status: str = "draft"
    notes: str | None = None
    recipient_import_text: str = ""


class NewsletterUpdateRequest(NewsletterCreateRequest):
    pass


class NewsletterDetail(NewsletterSummary):
    recipients: list[NewsletterRecipientSummary]
    recipient_import_text: str


class NewsletterPreviewResponse(BaseModel):
    subject: str
    preheader: str
    html: str
    plain_text: str
    template_key: str


class NewsletterTestSendRequest(BaseModel):
    to_email: str


class NewsletterTestSendResponse(BaseModel):
    status: str
    mode: str
    message: str
    provider_id: str | None = None
    to_email: str


class NewsletterRunSummary(BaseModel):
    id: int
    newsletter_id: int
    trigger_mode: str
    run_status: str
    provider_name: str
    model_name: str
    template_key: str
    recipient_count: int
    snapshot_subject: str
    snapshot_preheader: str | None
    snapshot_body_text: str
    snapshot_recipient_emails: str
    delivery_outcomes: str
    result_mode: str | None
    result_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NewsletterRunEventSummary(BaseModel):
    id: int
    event_type: str
    event_status: str
    message: str
    provider_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NewsletterGenerationResponse(BaseModel):
    status: str
    mode: str
    message: str
    newsletter: NewsletterDetail
    run: NewsletterRunSummary


class RecipientSendOutcomeResponse(BaseModel):
    email: str
    status: str
    provider_id: str | None
    detail: str


class NewsletterSendResponse(BaseModel):
    status: str
    mode: str
    message: str
    run: NewsletterRunSummary
    recipient_outcomes: list[RecipientSendOutcomeResponse]


class RunListResponse(BaseModel):
    items: list[NewsletterRunSummary]


class RunDetailResponse(BaseModel):
    run: NewsletterRunSummary
    newsletter: NewsletterSummary
    recipient_emails: list[str]
    recipient_outcomes: list[RecipientSendOutcomeResponse]
    events: list[NewsletterRunEventSummary]


class RunReconciliationResponse(BaseModel):
    events: list[NewsletterRunEventSummary]
