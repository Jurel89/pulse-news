from __future__ import annotations

import json
import os
from dataclasses import dataclass
from html import escape
from urllib import error, request

from app.config import Settings
from app.email_templates import RenderedNewsletter


@dataclass(frozen=True)
class RecipientDeliveryTarget:
    email: str
    unsubscribe_token: str | None = None


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


def _resend_headers(settings: Settings) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json",
    }


def _build_unsubscribe_url(unsubscribe_token: str | None) -> str | None:
    app_base_url = os.environ.get("PULSE_NEWS_BASE_URL", "").rstrip("/")
    if not app_base_url or not unsubscribe_token:
        return None
    return f"{app_base_url}/api/public/unsubscribe/{unsubscribe_token}"


def _append_unsubscribe_footer(
    *,
    rendered: RenderedNewsletter,
    unsubscribe_url: str | None,
) -> tuple[str, str]:
    if not unsubscribe_url:
        return rendered.html, rendered.plain_text

    unsubscribe_href = escape(unsubscribe_url, quote=True)
    footer_html = "".join(
        [
            '<div style="max-width:640px;margin:18px auto 0;padding:0 18px 24px;">',
            '<p style="margin:0;font-size:13px;line-height:1.6;color:#5c6b78;">',
            "You are receiving this email because you subscribed to this newsletter. ",
            f'<a href="{unsubscribe_href}" '
            'style="color:#18324a;text-decoration:underline;">Unsubscribe</a>.',
            "</p>",
            "</div>",
        ]
    )
    if "</body>" in rendered.html:
        html = rendered.html.replace("</body>", f"{footer_html}\n  </body>")
    else:
        html = f"{rendered.html}\n{footer_html}"

    plain_text = (
        f"{rendered.plain_text}\n\n---\n"
        "You are receiving this email because you subscribed to this newsletter.\n"
        f"Unsubscribe: {unsubscribe_url}"
    )
    return html, plain_text


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
    headers = _resend_headers(settings)

    send_request = request.Request(
        settings.resend_api_url,
        data=payload,
        headers=headers,
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
    recipient_targets: list[RecipientDeliveryTarget],
) -> ManualSendResult:
    if settings.environment == "production" and (
        not settings.resend_api_key or not settings.resend_from_email
    ):
        raise RuntimeError(
            "Cannot send emails in production without Resend configuration. "
            "Set PULSE_NEWS_RESEND_API_KEY and PULSE_NEWS_RESEND_FROM_EMAIL."
        )

    if not settings.resend_api_key or not settings.resend_from_email:
        return ManualSendResult(
            status="fallback",
            mode="local-preview",
            message=(
                "Resend is not configured; returning local preview delivery results "
                "for all recipients."
            ),
            recipient_outcomes=[
                RecipientSendOutcome(
                    email=target.email,
                    status="simulated",
                    provider_id=None,
                    detail="Local preview fallback",
                )
                for target in recipient_targets
            ],
        )

    outcomes: list[RecipientSendOutcome] = []
    headers = _resend_headers(settings)
    for target in recipient_targets:  # pragma: no cover - live network path not exercised in tests
        unsubscribe_url = _build_unsubscribe_url(target.unsubscribe_token)
        html_content, plain_text_content = _append_unsubscribe_footer(
            rendered=rendered,
            unsubscribe_url=unsubscribe_url,
        )
        payload_dict = {
            "from": settings.resend_from_email,
            "to": [target.email],
            "subject": rendered.subject,
            "html": html_content,
            "text": plain_text_content,
        }
        if unsubscribe_url:
            payload_dict["headers"] = {
                "List-Unsubscribe": f"<{unsubscribe_url}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            }
        payload = json.dumps(payload_dict).encode("utf-8")
        send_request = request.Request(
            settings.resend_api_url,
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(send_request, timeout=15) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
            outcomes.append(
                RecipientSendOutcome(
                    email=target.email,
                    status="sent",
                    provider_id=response_payload.get("id"),
                    detail="Sent through Resend",
                )
            )
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8")
            outcomes.append(
                RecipientSendOutcome(
                    email=target.email,
                    status="failed",
                    provider_id=None,
                    detail=f"Resend HTTP error: {detail}",
                )
            )
        except error.URLError as exc:
            outcomes.append(
                RecipientSendOutcome(
                    email=target.email,
                    status="failed",
                    provider_id=None,
                    detail=f"Resend connection error: {exc.reason}",
                )
            )

    if not outcomes:
        overall_status = "no_recipients"
        message = "No recipient emails were available for delivery."
    elif all(item.status == "sent" for item in outcomes):
        overall_status = "sent"
        message = "Delivered to all active recipients through Resend."
    elif any(item.status == "sent" for item in outcomes):
        overall_status = "partial"
        message = "Delivered to some active recipients, but one or more deliveries failed."
    else:
        overall_status = "failed"
        message = "Delivery failed for every active recipient."

    return ManualSendResult(
        status=overall_status,
        mode="resend",
        message=message,
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
