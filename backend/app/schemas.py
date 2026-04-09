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


class NewsletterSummary(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None
    prompt: str
    provider_name: str
    model_name: str
    template_key: str
    timezone: str
    schedule_cron: str | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
