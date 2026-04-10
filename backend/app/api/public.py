from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from starlette.responses import HTMLResponse

from app.database import get_session_maker
from app.models import NewsletterRecipient, utc_now

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
        session.commit()
        return {"status": "unsubscribed"}
    finally:
        session.close()


@public_router.get("/unsubscribe/{token}")
def unsubscribe_recipient_get(token: str) -> HTMLResponse:
    _perform_unsubscribe(token)
    return HTMLResponse(
        content="<html><body><h2>Unsubscribed</h2>"
        "<p>You have been successfully unsubscribed from this newsletter.</p>"
        "</body></html>"
    )


@public_router.post("/unsubscribe/{token}")
def unsubscribe_recipient_post(token: str, request: Request) -> dict[str, str]:
    return _perform_unsubscribe(token)
