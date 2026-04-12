from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from html import escape
from urllib import error, request

from app.config import Settings
from app.crypto import decrypt_secret
from app.email_templates import RenderedNewsletter
from app.models import Newsletter


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


RESEND_BATCH_CHUNK_SIZE = 100
RESEND_BATCH_MAX_ATTEMPTS = 3


def _get_resend_api_key(settings: Settings, newsletter: Newsletter | None = None) -> str | None:
    if newsletter and newsletter.resend_api_key_id:
        session_generator = None
        try:
            from sqlalchemy import select

            from app.deps import get_db_session
            from app.models import ApiKey

            session_generator = get_db_session()
            db = next(session_generator)
            api_key = db.scalar(
                select(ApiKey).where(
                    ApiKey.id == newsletter.resend_api_key_id,
                    ApiKey.is_active.is_(True),
                    ApiKey.provider_type == "resend",
                )
            )
            if api_key and api_key.key_value:
                return decrypt_secret(api_key.key_value)
        except Exception:
            pass
        finally:
            if session_generator is not None:
                session_generator.close()
    return settings.resend_api_key


def _get_resend_from_email(settings: Settings, newsletter: Newsletter | None = None) -> str | None:
    return settings.resend_from_email


def _resend_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
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


def _unsubscribe_headers(unsubscribe_url: str | None) -> dict[str, str] | None:
    if not unsubscribe_url:
        return None

    return {
        "List-Unsubscribe": f"<{unsubscribe_url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


def _build_recipient_payload(
    *,
    from_email: str,
    rendered: RenderedNewsletter,
    target: RecipientDeliveryTarget,
) -> dict[str, object]:
    unsubscribe_url = _build_unsubscribe_url(target.unsubscribe_token)
    html_content, plain_text_content = _append_unsubscribe_footer(
        rendered=rendered,
        unsubscribe_url=unsubscribe_url,
    )
    payload_dict: dict[str, object] = {
        "from": from_email,
        "to": [target.email],
        "subject": rendered.subject,
        "html": html_content,
        "text": plain_text_content,
    }
    unsubscribe_headers = _unsubscribe_headers(unsubscribe_url)
    if unsubscribe_headers:
        payload_dict["headers"] = unsubscribe_headers
    return payload_dict


def _decode_http_error_detail(exc: error.HTTPError) -> str:
    detail = exc.read().decode("utf-8", errors="replace").strip()
    if detail:
        return detail
    if exc.reason:
        return str(exc.reason)
    return f"HTTP {exc.code}"


def _failed_outcome(*, email: str, detail: str) -> RecipientSendOutcome:
    return RecipientSendOutcome(
        email=email,
        status="failed",
        provider_id=None,
        detail=detail,
    )


def _send_single_recipient_via_resend(
    *,
    api_key: str,
    from_email: str,
    resend_api_url: str,
    rendered: RenderedNewsletter,
    target: RecipientDeliveryTarget,
    attempt_key: str | None,
) -> RecipientSendOutcome:
    payload = json.dumps(
        _build_recipient_payload(
            from_email=from_email,
            rendered=rendered,
            target=target,
        )
    ).encode("utf-8")
    headers = _resend_headers(api_key)
    if attempt_key:
        headers["Idempotency-Key"] = f"{attempt_key}-{target.email}"

    send_request = request.Request(
        resend_api_url,
        data=payload,
        headers=headers,
        method="POST",
    )

    try:
        with request.urlopen(send_request, timeout=15) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
        return RecipientSendOutcome(
            email=target.email,
            status="sent",
            provider_id=response_payload.get("id"),
            detail="Sent through Resend",
        )
    except error.HTTPError as exc:
        return _failed_outcome(
            email=target.email,
            detail=f"Resend HTTP error: {_decode_http_error_detail(exc)}",
        )
    except error.URLError as exc:
        return _failed_outcome(
            email=target.email,
            detail=f"Resend connection error: {exc.reason}",
        )


def _batch_headers(
    api_key: str,
    *,
    idempotency_key: str | None,
) -> dict[str, str]:
    headers = _resend_headers(api_key)
    headers["x-batch-validation"] = "permissive"
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _map_batch_response_to_outcomes(
    *,
    recipient_targets: list[RecipientDeliveryTarget],
    response_payload: object,
) -> list[RecipientSendOutcome]:
    if not isinstance(response_payload, dict):
        return [
            _failed_outcome(
                email=target.email,
                detail="Resend batch response was not a JSON object.",
            )
            for target in recipient_targets
        ]

    response_data = response_payload.get("data")
    response_errors = response_payload.get("errors")
    provider_items = response_data if isinstance(response_data, list) else []
    error_messages_by_index: dict[int, str] = {}
    if isinstance(response_errors, list):
        for item in response_errors:
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            message = item.get("message")
            if isinstance(index, int):
                error_messages_by_index[index] = (
                    message if isinstance(message, str) and message else "Batch validation failed."
                )

    outcomes: list[RecipientSendOutcome] = []
    provider_item_index = 0
    for recipient_index, target in enumerate(recipient_targets):
        if recipient_index in error_messages_by_index:
            outcomes.append(
                _failed_outcome(
                    email=target.email,
                    detail=(
                        f"Resend batch validation error: {error_messages_by_index[recipient_index]}"
                    ),
                )
            )
            continue

        provider_item = (
            provider_items[provider_item_index]
            if provider_item_index < len(provider_items)
            else None
        )
        provider_item_index += 1
        provider_id = provider_item.get("id") if isinstance(provider_item, dict) else None
        if provider_id:
            outcomes.append(
                RecipientSendOutcome(
                    email=target.email,
                    status="sent",
                    provider_id=provider_id,
                    detail="Sent through Resend",
                )
            )
            continue

        outcomes.append(
            _failed_outcome(
                email=target.email,
                detail="Resend batch response was missing an email id.",
            )
        )

    return outcomes


def _send_recipient_chunk_via_resend_batch(
    *,
    api_key: str,
    from_email: str,
    resend_api_base_url: str,
    rendered: RenderedNewsletter,
    recipient_targets: list[RecipientDeliveryTarget],
    chunk_index: int,
    attempt_key: str | None,
) -> list[RecipientSendOutcome]:
    payload_items = [
        _build_recipient_payload(
            from_email=from_email,
            rendered=rendered,
            target=target,
        )
        for target in recipient_targets
    ]
    payload = json.dumps(payload_items).encode("utf-8")
    batch_url = f"{resend_api_base_url}/emails/batch"
    idempotency_key = f"{attempt_key}-chunk-{chunk_index}" if attempt_key else None

    for attempt_number in range(1, RESEND_BATCH_MAX_ATTEMPTS + 1):
        send_request = request.Request(
            batch_url,
            data=payload,
            headers=_batch_headers(api_key, idempotency_key=idempotency_key),
            method="POST",
        )
        try:
            with request.urlopen(send_request, timeout=15) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
            return _map_batch_response_to_outcomes(
                recipient_targets=recipient_targets,
                response_payload=response_payload,
            )
        except error.HTTPError as exc:
            detail = _decode_http_error_detail(exc)
            if exc.code == 429 and attempt_number < RESEND_BATCH_MAX_ATTEMPTS:
                time.sleep(attempt_number)
                continue
            return [
                _failed_outcome(
                    email=target.email,
                    detail=f"Resend HTTP error: {detail}",
                )
                for target in recipient_targets
            ]
        except error.URLError as exc:
            return [
                _failed_outcome(
                    email=target.email,
                    detail=f"Resend connection error: {exc.reason}",
                )
                for target in recipient_targets
            ]

    return [
        _failed_outcome(
            email=target.email,
            detail="Resend batch delivery exhausted all retry attempts.",
        )
        for target in recipient_targets
    ]


def send_test_email(
    *,
    settings: Settings,
    rendered: RenderedNewsletter,
    to_email: str,
    newsletter: Newsletter | None = None,
) -> TestSendResult:
    api_key = _get_resend_api_key(settings, newsletter)
    from_email = _get_resend_from_email(settings, newsletter)

    if not api_key or not from_email:
        if settings.environment == "production":
            raise RuntimeError(
                "Cannot test-send in production without Resend configuration. "
                "Set PULSE_NEWS_RESEND_API_KEY and PULSE_NEWS_RESEND_FROM_EMAIL "
                "or configure a Resend API key for this newsletter."
            )
        return TestSendResult(
            status="simulated",
            mode="local-preview",
            message=(
                "Resend is not configured; this is a local preview-only "
                "result, not a real delivery test."
            ),
            provider_id=None,
            to_email=to_email,
        )

    payload = json.dumps(
        {
            "from": from_email,
            "to": [to_email],
            "subject": rendered.subject,
            "html": rendered.html,
            "text": rendered.plain_text,
        }
    ).encode("utf-8")
    headers = _resend_headers(api_key)

    send_request = request.Request(
        settings.resend_api_url,
        data=payload,
        headers=headers,
        method="POST",
    )

    try:
        with request.urlopen(send_request, timeout=15) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"Resend test send failed: {detail}") from exc
    except error.URLError as exc:
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
    attempt_key: str | None = None,
    newsletter: Newsletter | None = None,
) -> ManualSendResult:
    api_key = _get_resend_api_key(settings, newsletter)
    from_email = _get_resend_from_email(settings, newsletter)

    if settings.environment == "production" and (not api_key or not from_email):
        raise RuntimeError(
            "Cannot send emails in production without Resend configuration. "
            "Set PULSE_NEWS_RESEND_API_KEY and PULSE_NEWS_RESEND_FROM_EMAIL "
            "or configure a Resend API key for this newsletter."
        )

    if not api_key or not from_email:
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
    if len(recipient_targets) == 1:
        outcomes.append(
            _send_single_recipient_via_resend(
                api_key=api_key,
                from_email=from_email,
                resend_api_url=settings.resend_api_url,
                rendered=rendered,
                target=recipient_targets[0],
                attempt_key=attempt_key,
            )
        )
    else:
        for chunk_start in range(0, len(recipient_targets), RESEND_BATCH_CHUNK_SIZE):
            chunk_targets = recipient_targets[chunk_start : chunk_start + RESEND_BATCH_CHUNK_SIZE]
            outcomes.extend(
                _send_recipient_chunk_via_resend_batch(
                    api_key=api_key,
                    from_email=from_email,
                    resend_api_base_url=settings.resend_api_base_url,
                    rendered=rendered,
                    recipient_targets=chunk_targets,
                    chunk_index=(chunk_start // RESEND_BATCH_CHUNK_SIZE) + 1,
                    attempt_key=attempt_key,
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
    newsletter: Newsletter | None = None,
) -> ReconciliationEvent:
    if current_mode != "resend" or not provider_id:
        return ReconciliationEvent(
            event_status="simulated",
            message="No live provider status is available for this delivery outcome.",
            provider_id=provider_id,
        )

    api_key = _get_resend_api_key(settings, newsletter)
    if not api_key:
        return ReconciliationEvent(
            event_status="unknown",
            message="Cannot retrieve status without Resend API key.",
            provider_id=provider_id,
        )

    retrieve_request = request.Request(
        f"{settings.resend_api_base_url}/emails/{provider_id}",
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )

    try:
        with request.urlopen(retrieve_request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return ReconciliationEvent(
            event_status=payload.get("last_event", "unknown"),
            message="Delivery status retrieved from Resend.",
            provider_id=provider_id,
        )
    except Exception as exc:
        return ReconciliationEvent(
            event_status="unknown",
            message=f"Unable to retrieve live delivery status: {exc}",
            provider_id=provider_id,
        )
