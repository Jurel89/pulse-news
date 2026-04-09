from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import error, request

from app.config import Settings
from app.email_templates import RenderedNewsletter


@dataclass
class TestSendResult:
    status: str
    mode: str
    message: str
    provider_id: str | None
    to_email: str


@dataclass
class RecipientSendOutcome:
    email: str
    status: str
    provider_id: str | None
    detail: str


@dataclass
class ManualSendResult:
    status: str
    mode: str
    message: str
    recipient_outcomes: list[RecipientSendOutcome]


@dataclass
class ReconciliationEvent:
    event_status: str
    message: str
    provider_id: str | None


def send_test_email(
    *,
    settings: Settings,
    rendered: RenderedNewsletter,
    to_email: str,
) -> TestSendResult:
    if not settings.resend_api_key or not settings.resend_from_email:
        return TestSendResult(
            status="simulated",
            mode="local-preview",
            message="Resend is not configured; returning a local preview-only test-send result.",
            provider_id=None,
            to_email=to_email,
        )

    payload = json.dumps(
        {
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": rendered.subject,
            "html": rendered.html,
            "text": rendered.plain_text,
        }
    ).encode("utf-8")

    send_request = request.Request(
        settings.resend_api_url,
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(send_request, timeout=15) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:  # pragma: no cover - network path not exercised in tests
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"Resend test send failed: {detail}") from exc
    except error.URLError as exc:  # pragma: no cover - network path not exercised in tests
        raise RuntimeError(f"Resend test send failed: {exc.reason}") from exc

    return TestSendResult(
        status="sent",
        mode="resend",
        message="Test email sent successfully through Resend.",
        provider_id=response_payload.get("id"),
        to_email=to_email,
    )


def send_newsletter_email(
    *,
    settings: Settings,
    rendered: RenderedNewsletter,
    recipient_emails: list[str],
) -> ManualSendResult:
    if not settings.resend_api_key or not settings.resend_from_email:
        return ManualSendResult(
            status="fallback",
            mode="local-preview",
            message=(
                "Resend is not configured; returning local preview delivery "
                "results for all recipients."
            ),
            recipient_outcomes=[
                RecipientSendOutcome(
                    email=email,
                    status="simulated",
                    provider_id=None,
                    detail="Local preview fallback",
                )
                for email in recipient_emails
            ],
        )

    outcomes: list[RecipientSendOutcome] = []
    for email in recipient_emails:  # pragma: no cover - live network path not exercised in tests
        payload = json.dumps(
            {
                "from": settings.resend_from_email,
                "to": [email],
                "subject": rendered.subject,
                "html": rendered.html,
                "text": rendered.plain_text,
            }
        ).encode("utf-8")
        send_request = request.Request(
            settings.resend_api_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(send_request, timeout=15) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
            outcomes.append(
                RecipientSendOutcome(
                    email=email,
                    status="sent",
                    provider_id=response_payload.get("id"),
                    detail="Sent through Resend",
                )
            )
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8")
            outcomes.append(
                RecipientSendOutcome(
                    email=email,
                    status="failed",
                    provider_id=None,
                    detail=f"Resend HTTP error: {detail}",
                )
            )
        except error.URLError as exc:
            outcomes.append(
                RecipientSendOutcome(
                    email=email,
                    status="failed",
                    provider_id=None,
                    detail=f"Resend connection error: {exc.reason}",
                )
            )

    overall_status = "sent" if all(item.status == "sent" for item in outcomes) else "partial"
    return ManualSendResult(
        status=overall_status,
        mode="resend",
        message="Manual send attempted for all active recipients.",
        recipient_outcomes=outcomes,
    )


def retrieve_email_status(
    *,
    settings: Settings,
    provider_id: str | None,
    current_mode: str | None,
) -> ReconciliationEvent:
    if current_mode != "resend" or not provider_id:
        return ReconciliationEvent(
            event_status="simulated",
            message="No live provider status is available for this delivery outcome.",
            provider_id=provider_id,
        )

    retrieve_request = request.Request(
        f"{settings.resend_api_base_url}/emails/{provider_id}",
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        method="GET",
    )

    try:  # pragma: no cover - live network path not exercised in tests
        with request.urlopen(retrieve_request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return ReconciliationEvent(
            event_status=payload.get("last_event", "unknown"),
            message="Delivery status retrieved from Resend.",
            provider_id=provider_id,
        )
    except Exception as exc:  # pragma: no cover - local tests exercise fallback path
        return ReconciliationEvent(
            event_status="unknown",
            message=f"Unable to retrieve live delivery status: {exc}",
            provider_id=provider_id,
        )
