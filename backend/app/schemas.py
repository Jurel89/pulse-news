from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

try:  # pragma: no cover - depends on local environment extras
    import email_validator  # noqa: F401
except ImportError:  # pragma: no cover - exercised in the repo test venv
    EmailStr = Annotated[
        str,
        StringConstraints(strip_whitespace=True, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
    ]
else:  # pragma: no cover - exercised when pydantic[email] is installed
    from pydantic import EmailStr


class NewsletterStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class TemplateKey(StrEnum):
    SIGNAL = "signal"
    LEDGER = "ledger"


class SupportedProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    GOOGLE = "google"
    OPENROUTER = "openrouter"


CRON_5_FIELD_PATTERN = re.compile(r"^\S+(?:\s+\S+){4}$")


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
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


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
    delivery_topic: str
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
    template_key: TemplateKey = TemplateKey.SIGNAL
    audience_name: str = "default-audience"
    delivery_topic: str = "default-topic"
    timezone: str = "UTC"
    schedule_enabled: bool = False
    schedule_cron: str | None = None
    status: NewsletterStatus = NewsletterStatus.DRAFT
    notes: str | None = None
    recipient_import_text: str = ""

    @field_validator("provider_name")
    @classmethod
    def validate_provider_name(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in SupportedProvider._value2member_map_:
            supported = ", ".join(provider.value for provider in SupportedProvider)
            raise ValueError(f"provider_name must be one of: {supported}.")
        return normalized

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("timezone must not be empty.")
        try:
            ZoneInfo(normalized)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone.") from exc
        return normalized

    @field_validator("schedule_cron")
    @classmethod
    def validate_schedule_cron(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = " ".join(value.split())
        if not normalized:
            return None
        if CRON_5_FIELD_PATTERN.fullmatch(normalized) is None:
            raise ValueError("schedule_cron must be a valid 5-field cron expression.")
        return normalized

    @model_validator(mode="after")
    def validate_schedule_state(self) -> NewsletterCreateRequest:
        if self.schedule_enabled and not self.schedule_cron:
            raise ValueError("schedule_cron is required when schedule_enabled is true.")
        if self.schedule_enabled and self.status != NewsletterStatus.ACTIVE:
            raise ValueError("status must be 'active' when schedule_enabled is true.")
        return self


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
    to_email: EmailStr


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
    # Snapshot captured at run time; older runs may not have a full newsletter snapshot.
    newsletter_snapshot: NewsletterSummary | None = None
    recipient_emails: list[str]
    recipient_outcomes: list[RecipientSendOutcomeResponse]
    events: list[NewsletterRunEventSummary]


class RunReconciliationResponse(BaseModel):
    events: list[NewsletterRunEventSummary]
