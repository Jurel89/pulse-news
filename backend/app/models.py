from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
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
    provider_name: Mapped[str] = mapped_column(String(255), default="openai", nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), default="gpt-4o-mini", nullable=False)
    template_key: Mapped[str] = mapped_column(String(255), default="signal", nullable=False)
    audience_name: Mapped[str] = mapped_column(
        String(255),
        default="default-audience",
        nullable=False,
    )
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    schedule_cron: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    recipients: Mapped[list[NewsletterRecipient]] = relationship(
        back_populates="newsletter",
        cascade="all, delete-orphan",
    )


class NewsletterRecipient(TimestampMixin, Base):
    __tablename__ = "newsletter_recipients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    newsletter_id: Mapped[int] = mapped_column(
        ForeignKey("newsletters.id"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    unsubscribe_token: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    newsletter: Mapped[Newsletter] = relationship(back_populates="recipients")


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
