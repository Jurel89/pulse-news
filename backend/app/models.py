from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=utc_now,
        onupdate=utc_now,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)


class SystemSettings(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    initialized: Mapped[bool] = mapped_column(default=False, nullable=False)
    operator_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bootstrap_disabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class EmailTemplate(TimestampMixin, Base):
    __tablename__ = "email_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    html_template: Mapped[str] = mapped_column(Text(), nullable=False)
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_system: Mapped[bool] = mapped_column(default=False, nullable=False)
    newsletters: Mapped[list[Newsletter]] = relationship(back_populates="template")


class Provider(TimestampMixin, Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    default_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    configuration: Mapped[str | None] = mapped_column(Text(), nullable=True)
    newsletters: Mapped[list[Newsletter]] = relationship(back_populates="provider")


class ApiKey(TimestampMixin, Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    key_value: Mapped[str] = mapped_column(Text(), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    newsletters: Mapped[list[Newsletter]] = relationship(
        back_populates="api_key",
        foreign_keys="Newsletter.api_key_id",
    )
    resend_newsletters: Mapped[list[Newsletter]] = relationship(
        back_populates="resend_api_key",
        foreign_keys="Newsletter.resend_api_key_id",
    )


class Newsletter(TimestampMixin, Base):
    __tablename__ = "newsletters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    prompt: Mapped[str] = mapped_column(Text(), default="", nullable=False)
    draft_subject: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    draft_preheader: Mapped[str | None] = mapped_column(String(255), nullable=True)
    draft_body_text: Mapped[str] = mapped_column(Text(), default="", nullable=False)
    provider_id: Mapped[int | None] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider_name: Mapped[str] = mapped_column(String(255), default="openai", nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), default="gpt-4o-mini", nullable=False)
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("email_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    template_key: Mapped[str] = mapped_column(String(255), default="signal", nullable=False)
    api_key_id: Mapped[int | None] = mapped_column(
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resend_api_key_id: Mapped[int | None] = mapped_column(
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    audience_name: Mapped[str] = mapped_column(
        String(255),
        default="default-audience",
        nullable=False,
    )
    delivery_topic: Mapped[str] = mapped_column(
        String(255),
        default="default-topic",
        nullable=False,
    )
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    schedule_cron: Mapped[str | None] = mapped_column(String(255), nullable=True)
    schedule_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    template: Mapped[EmailTemplate | None] = relationship(back_populates="newsletters")
    provider: Mapped[Provider | None] = relationship(back_populates="newsletters")
    api_key: Mapped[ApiKey | None] = relationship(
        back_populates="newsletters",
        foreign_keys=[api_key_id],
    )
    resend_api_key: Mapped[ApiKey | None] = relationship(
        back_populates="resend_newsletters",
        foreign_keys=[resend_api_key_id],
    )
    recipients: Mapped[list[NewsletterRecipient]] = relationship(
        back_populates="newsletter",
        cascade="all, delete-orphan",
    )
    runs: Mapped[list[NewsletterRun]] = relationship(
        back_populates="newsletter",
        cascade="all",
    )


class NewsletterRecipient(TimestampMixin, Base):
    __tablename__ = "newsletter_recipients"
    __table_args__ = (
        UniqueConstraint("newsletter_id", "email", name="uq_newsletter_recipient_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    newsletter_id: Mapped[int] = mapped_column(
        ForeignKey("newsletters.id"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="subscribed", nullable=False)
    unsubscribe_token: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suppression_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    newsletter: Mapped[Newsletter] = relationship(back_populates="recipients")


class NewsletterRun(TimestampMixin, Base):
    __tablename__ = "newsletter_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    newsletter_id: Mapped[int] = mapped_column(
        ForeignKey("newsletters.id"),
        nullable=False,
        index=True,
    )
    trigger_mode: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_key: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snapshot_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    snapshot_preheader: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snapshot_body_text: Mapped[str] = mapped_column(Text(), nullable=False)
    snapshot_recipient_emails: Mapped[str] = mapped_column(Text(), nullable=False, default="[]")
    delivery_outcomes: Mapped[str] = mapped_column(Text(), nullable=False, default="[]")
    result_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    attempt_key: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    rendered_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rendered_preheader: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rendered_html: Mapped[str | None] = mapped_column(Text(), nullable=True)
    rendered_plain_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    snapshot_prompt: Mapped[str | None] = mapped_column(Text(), nullable=True)
    snapshot_newsletter_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snapshot_newsletter_slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snapshot_delivery_topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snapshot_status_at_run: Mapped[str | None] = mapped_column(String(32), nullable=True)
    newsletter: Mapped[Newsletter] = relationship(back_populates="runs")
    events: Mapped[list[NewsletterRunEvent]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class NewsletterRunEvent(Base):
    __tablename__ = "newsletter_run_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("newsletter_runs.id"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_status: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text(), nullable=False)
    provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=utc_now,
    )
    run: Mapped[NewsletterRun] = relationship(back_populates="events")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text(), nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=utc_now,
    )
