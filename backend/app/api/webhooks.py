from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.config import get_settings
from app.database import get_session_maker
from app.models import NewsletterRecipient, NewsletterRunEvent, utc_now

logger = logging.getLogger(__name__)
webhooks_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def verify_resend_signature(*, payload: bytes, signature: str, timestamp: str) -> bool:
    """Verify Resend webhook signature using HMAC-SHA256."""
    settings = get_settings()
    webhook_secret = settings.resend_webhook_secret
    if not webhook_secret:
        if settings.environment == "production":
            logger.warning("Missing Resend webhook secret in production")
            return False
        logger.warning("No webhook secret configured, skipping verification")
        return True
    if not signature or not timestamp:
        return False

    signed_message = f"{timestamp}.{payload.decode('utf-8')}"
    expected_signature = hmac.new(
        webhook_secret.encode("utf-8"),
        signed_message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)


def _extract_email_address(raw_to: object) -> str:
    if isinstance(raw_to, list):
        first_recipient = raw_to[0] if raw_to else ""
        return first_recipient if isinstance(first_recipient, str) else ""
    if isinstance(raw_to, str):
        return raw_to
    return ""


@webhooks_router.post("/resend")
async def handle_resend_webhook(request: Request) -> dict[str, str]:
    """Handle incoming Resend webhook events."""
    body = await request.body()
    signature = request.headers.get("resend-signature", "")
    timestamp = request.headers.get("resend-timestamp", "")

    if not verify_resend_signature(payload=body, signature=signature, timestamp=timestamp):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature.",
        )

    try:
        event = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        ) from exc

    event_type = event.get("type", "")
    data = event.get("data", {})
    provider_event_id = data.get("email_id") or data.get("id") or ""

    session = get_session_maker()()
    try:
        if provider_event_id:
            existing = session.scalar(
                select(NewsletterRunEvent).where(
                    NewsletterRunEvent.provider_id == provider_event_id,
                    NewsletterRunEvent.event_type == f"webhook:{event_type}",
                )
            )
            if existing is not None:
                logger.debug("Deduplicating already-processed event %s", provider_event_id)
                return {"status": "deduplicated"}

        if event_type in {"email.bounced", "email.complained"}:
            email_address = _extract_email_address(data.get("to"))
            if email_address:
                recipients = session.scalars(
                    select(NewsletterRecipient).where(NewsletterRecipient.email == email_address)
                ).all()
                reason = "bounce" if event_type == "email.bounced" else "complaint"
                for recipient in recipients:
                    if recipient.status in ("subscribed",):
                        recipient.is_active = False
                        recipient.status = f"suppressed_{reason}"
                        recipient.suppression_reason = reason
                        recipient.unsubscribed_at = utc_now()
                        session.add(recipient)

                if recipients:
                    logger.info("Suppressed %s recipient(s) for %s", len(recipients), email_address)
                else:
                    logger.info("Received %s for unknown recipient %s", reason, email_address)
        elif event_type == "email.delivered":
            logger.debug("Email delivered: %s", provider_event_id)

        if provider_event_id:
            dedup_event = NewsletterRunEvent(
                run_id=0,
                event_type=f"webhook:{event_type}",
                event_status="processed",
                message=json.dumps({"type": event_type, "email": data.get("to")}),
                provider_id=provider_event_id,
            )
            session.add(dedup_event)

        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed to process webhook event: %s", event_type)
        raise
    finally:
        session.close()

    return {"status": "processed"}
