from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)

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
    RESEND = "resend"
    ZAI = "zai"
    KIMI = "kimi"


CRON_5_FIELD_PATTERN = re.compile(r"^\S+(?:\s+\S+){4}$")
RESOURCE_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def _normalize_required_text(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_optional_email(value: str | None, *, field_name: str) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    local_part, separator, domain = normalized.partition("@")
    if not separator or not local_part or "." not in domain:
        raise ValueError(f"{field_name} must be a valid email address.")
    return normalized


def _validate_supported_provider_name(value: str, *, field_name: str) -> str:
    normalized = _normalize_required_text(value, field_name=field_name).lower()
    if normalized not in SupportedProvider._value2member_map_:
        supported = ", ".join(provider.value for provider in SupportedProvider)
        raise ValueError(f"{field_name} must be one of: {supported}.")
    return normalized


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
    bootstrap_secret: str | None = None


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
    provider_id: int | None = None
    provider_name: str
    model_name: str
    template_key: str
    api_key_id: int | None = None
    resend_api_key_id: int | None = None
    generation_profile_id: int | None = None
    delivery_profile_id: int | None = None
    approved_revision_id: int | None = None
    draft_head_revision_id: int | None = None
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
    prompt: str
    draft_subject: str
    draft_preheader: str | None = None
    draft_body_text: str
    provider_id: int | None = None
    provider_name: str
    model_name: str
    template_key: str
    api_key_id: int | None = None
    resend_api_key_id: int | None = None
    generation_profile_id: int | None = None
    delivery_profile_id: int | None = None
    audience_name: str
    delivery_topic: str
    timezone: str
    schedule_enabled: bool
    schedule_cron: str | None = None
    status: NewsletterStatus
    notes: str | None = None
    recipient_import_text: str

    @field_validator("name", "model_name", "template_key")
    @classmethod
    def validate_required_text_fields(cls, value: str, info: ValidationInfo) -> str:
        return _normalize_required_text(value, field_name=info.field_name)

    @field_validator("provider_name")
    @classmethod
    def validate_provider_name(cls, value: str) -> str:
        return _validate_supported_provider_name(value, field_name="provider_name")

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


class NewsletterJobUpdateRequest(BaseModel):
    name: str
    description: str | None = None
    prompt: str
    provider_id: int | None = None
    provider_name: str
    model_name: str
    template_key: str
    api_key_id: int | None = None
    resend_api_key_id: int | None = None
    generation_profile_id: int | None = None
    delivery_profile_id: int | None = None
    audience_name: str
    delivery_topic: str
    timezone: str
    schedule_enabled: bool
    schedule_cron: str | None = None
    status: NewsletterStatus
    notes: str | None = None
    recipient_import_text: str

    @field_validator("name", "model_name", "template_key")
    @classmethod
    def validate_required_text_fields(cls, value: str, info: ValidationInfo) -> str:
        return _normalize_required_text(value, field_name=info.field_name)

    @field_validator("provider_name")
    @classmethod
    def validate_provider_name(cls, value: str) -> str:
        return _validate_supported_provider_name(value, field_name="provider_name")

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
    def validate_schedule_state(self) -> NewsletterJobUpdateRequest:
        if self.schedule_enabled and not self.schedule_cron:
            raise ValueError("schedule_cron is required when schedule_enabled is true.")
        if self.schedule_enabled and self.status != NewsletterStatus.ACTIVE:
            raise ValueError("status must be 'active' when schedule_enabled is true.")
        return self


class NewsletterDetail(NewsletterSummary):
    recipients: list[NewsletterRecipientSummary]
    recipient_import_text: str


class DraftRevisionSummary(BaseModel):
    id: int
    newsletter_id: int
    version_number: int
    state: str
    origin: str
    created_by_email: str | None = None
    subject: str
    preheader: str | None = None
    body_text: str
    source_bundle_snapshot_json: str | None = None
    generation_run_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DraftRevisionListResponse(BaseModel):
    items: list[DraftRevisionSummary]


class DraftRevisionApproveResponse(BaseModel):
    revision: DraftRevisionSummary
    newsletter: NewsletterDetail


class DraftRevisionUpdateRequest(BaseModel):
    subject: str
    preheader: str | None = None
    body_text: str


class DraftRevisionDetailResponse(BaseModel):
    revision: DraftRevisionSummary


class EmailTemplateSummary(BaseModel):
    id: int
    name: str
    key: str
    description: str | None
    is_default: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EmailTemplateDetail(EmailTemplateSummary):
    html_template: str


class EmailTemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    key: str = Field(min_length=1, max_length=255)
    description: str | None = None
    html_template: str = Field(min_length=1)
    is_default: bool = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _normalize_required_text(value, field_name="name")

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        normalized = _normalize_required_text(value, field_name="key").lower()
        if RESOURCE_KEY_PATTERN.fullmatch(normalized) is None:
            raise ValueError(
                "key must start with a letter or number and contain only lowercase "
                "letters, numbers, hyphens, or underscores."
            )
        return normalized

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)

    @field_validator("html_template")
    @classmethod
    def validate_html_template(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("html_template must not be empty.")
        return normalized


class EmailTemplateUpdateRequest(EmailTemplateCreateRequest):
    pass


class EmailTemplatePreviewRequest(BaseModel):
    variables: dict[str, str] = Field(default_factory=dict)


class EmailTemplatePreviewResponse(BaseModel):
    html: str


class ProviderSummary(BaseModel):
    id: int
    name: str
    provider_type: str
    is_enabled: bool
    description: str | None
    default_model: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProviderDetail(ProviderSummary):
    configuration: str | None


class ProviderCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    provider_type: str = Field(min_length=1, max_length=64)
    is_enabled: bool = False
    description: str | None = None
    default_model: str | None = None
    configuration: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _normalize_required_text(value, field_name="name")

    @field_validator("provider_type")
    @classmethod
    def validate_provider_type(cls, value: str) -> str:
        return _validate_supported_provider_name(value, field_name="provider_type")

    @field_validator("description", "default_model", "configuration")
    @classmethod
    def validate_optional_text_fields(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)


class ProviderUpdateRequest(ProviderCreateRequest):
    pass


class ProviderModelsResponse(BaseModel):
    models: list[str]
    default_model: str | None = None
    verified_model: str | None = None
    verification_message: str | None = None


class ProviderTestResponse(BaseModel):
    status: str
    message: str
    provider_type: str
    default_model: str | None = None
    has_active_api_key: bool


class ApiKeySummary(BaseModel):
    id: int
    name: str
    provider_type: str
    masked_key: str
    from_email: str | None = None
    is_active: bool
    last_used_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyDetail(ApiKeySummary):
    pass


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    provider_type: str = Field(min_length=1, max_length=64)
    key_value: str = Field(min_length=1)
    from_email: str | None = None
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _normalize_required_text(value, field_name="name")

    @field_validator("provider_type")
    @classmethod
    def validate_provider_type(cls, value: str) -> str:
        return _validate_supported_provider_name(value, field_name="provider_type")

    @field_validator("key_value")
    @classmethod
    def validate_key_value(cls, value: str) -> str:
        return _normalize_required_text(value, field_name="key_value")

    @field_validator("from_email")
    @classmethod
    def validate_from_email(cls, value: str | None) -> str | None:
        return _normalize_optional_email(value, field_name="from_email")


class ApiKeyUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    provider_type: str = Field(min_length=1, max_length=64)
    key_value: str | None = None
    from_email: str | None = None
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _normalize_required_text(value, field_name="name")

    @field_validator("provider_type")
    @classmethod
    def validate_provider_type(cls, value: str) -> str:
        return _validate_supported_provider_name(value, field_name="provider_type")

    @field_validator("key_value")
    @classmethod
    def validate_key_value(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_required_text(value, field_name="key_value")

    @field_validator("from_email")
    @classmethod
    def validate_from_email(cls, value: str | None) -> str | None:
        return _normalize_optional_email(value, field_name="from_email")


class ApiKeyTestResponse(BaseModel):
    status: str
    message: str
    provider_type: str
    masked_key: str


class NewsletterPreviewResponse(BaseModel):
    subject: str
    preheader: str
    html: str
    plain_text: str
    template_key: str


class NewsletterTestSendRequest(BaseModel):
    to_email: EmailStr
    revision_id: int | None = None


class NewsletterSendRequest(BaseModel):
    revision_id: int | None = None
    idempotency_key: str | None = None


class NewsletterTestSendResponse(BaseModel):
    status: str
    mode: str
    message: str
    provider_id: str | None = None
    to_email: str


class NewsletterRunSummary(BaseModel):
    id: int
    newsletter_id: int
    revision_id: int | None = None
    run_type: str | None = None
    snapshot_newsletter_name: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
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
    revision_id: int | None = None
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


class OperationalEventSummary(BaseModel):
    id: str
    source: str
    source_id: int
    run_id: int
    newsletter_id: int
    newsletter_name: str | None = None
    newsletter_slug: str | None = None
    event_type: str
    status: str
    message: str
    related_entity: str
    trigger_mode: str | None = None
    recipient_count: int | None = None
    provider_id: str | None = None
    created_at: datetime


class OperationalEventListResponse(BaseModel):
    items: list[OperationalEventSummary]


class AuditEventSummary(BaseModel):
    id: int
    actor_email: str | None = None
    action: str
    entity_type: str
    entity_id: str
    summary: str
    payload_json: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditEventListResponse(BaseModel):
    items: list[AuditEventSummary]
