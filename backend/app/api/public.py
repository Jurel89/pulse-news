from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from starlette.responses import HTMLResponse, PlainTextResponse, Response

from app.database import get_session_maker
from app.models import AuditEvent, NewsletterRecipient, utc_now

public_router = APIRouter(prefix="/public", tags=["public"])


def _perform_unsubscribe(token: str) -> dict[str, str]:
    session = get_session_maker()()
    try:
        recipient = session.scalar(
            select(NewsletterRecipient).where(NewsletterRecipient.unsubscribe_token == token)
        )
        if recipient is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Unsubscribe token not found.",
            )

        recipient.is_active = False
        recipient.status = "unsubscribed"
        recipient.unsubscribed_at = utc_now()
        recipient.suppression_reason = "user_unsubscribed"
        session.add(recipient)
        session.add(
            AuditEvent(
                actor_email=None,
                action="recipient.unsubscribed",
                entity_type="newsletter_recipient",
                entity_id=str(recipient.id),
                summary=f"Recipient {recipient.email} unsubscribed via public link",
                payload_json=f'{{"newsletter_id": {recipient.newsletter_id}}}',
            )
        )
        session.commit()
        return {"status": "unsubscribed"}
    finally:
        session.close()


@public_router.get("/unsubscribe/{token}")
def unsubscribe_recipient_get(token: str) -> HTMLResponse:
    session = get_session_maker()()
    try:
        recipient = session.scalar(
            select(NewsletterRecipient).where(NewsletterRecipient.unsubscribe_token == token)
        )
    finally:
        session.close()

    if recipient is None:
        return HTMLResponse(
            content="<html><body><h2>Not Found</h2>"
            "<p>This unsubscribe link is invalid or has expired.</p>"
            "</body></html>",
            status_code=404,
        )

    if recipient.unsubscribed_at is not None:
        return HTMLResponse(
            content="<html><body><h2>Already Unsubscribed</h2>"
            "<p>You have already been unsubscribed from this newsletter.</p>"
            "</body></html>"
        )

    return HTMLResponse(
        content="<html><body><h2>Confirm Unsubscribe</h2>"
        "<p>Are you sure you want to unsubscribe from this newsletter?</p>"
        '<form method="POST" action="">'
        '<button type="submit">Yes, unsubscribe me</button>'
        "</form>"
        "</body></html>"
    )


@public_router.post("/unsubscribe/{token}")
def unsubscribe_recipient_post(token: str, request: Request) -> Response:
    _perform_unsubscribe(token)
    content_type = (request.headers.get("content-type") or "").lower()
    if "form" not in content_type:
        return PlainTextResponse(content="", status_code=status.HTTP_200_OK)
    return HTMLResponse(
        content="<html><body><h2>Unsubscribed</h2>"
        "<p>You have been successfully unsubscribed from this newsletter.</p>"
        "</body></html>"
    )
