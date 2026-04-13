from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from html import escape
from urllib import error, request

from app.config import Settings
from app.crypto import decrypt_secret
from app.email_templates import RenderedNewsletter
from app.models import ApiKey, Newsletter

logger = logging.getLogger(__name__)


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


@dataclass(frozen=True)
class ResendConfigurationResolution:
    api_key: str | None
    from_email: str | None
    api_key_source: str
    detail: str


RESEND_BATCH_CHUNK_SIZE = 100
RESEND_BATCH_MAX_ATTEMPTS = 3
SIMULATED_EMAIL_DELIVERY_ENV_VAR = "PULSE_NEWS_ALLOW_SIMULATED_EMAIL_DELIVERY"


def _normalize_config_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _load_resend_api_key_record(*, api_key_id: int | None = None, db_session=None) -> ApiKey | None:
    from sqlalchemy import select

    from app.database import get_session_maker
    from app.models import ApiKey

    owns_session = db_session is None
    session = db_session or get_session_maker()()

    try:
        if api_key_id is None:
            return None
        return session.scalar(select(ApiKey).where(ApiKey.id == api_key_id))
    finally:
        if owns_session:
            session.close()


def _resolve_resend_configuration(
    settings: Settings,
    newsletter: Newsletter | None = None,
    *,
    db_session=None,
) -> ResendConfigurationResolution:
    if newsletter and newsletter.resend_api_key_id is not None:
        detail_parts: list[str] = []
        try:
            stored_key = _load_resend_api_key_record(
                api_key_id=newsletter.resend_api_key_id,
                db_session=db_session,
            )
        except Exception as exc:
            logger.warning(
                "Failed to load newsletter Resend API key id=%s for newsletter id=%s: %s",
                newsletter.resend_api_key_id,
                newsletter.id,
                exc,
            )
            detail_parts.append(
                "The selected newsletter-specific Resend API key "
                "could not be loaded from the database."
            )
        else:
            if stored_key is None:
                logger.warning(
                    "Newsletter id=%s references missing Resend API key id=%s",
                    newsletter.id,
                    newsletter.resend_api_key_id,
                )
                detail_parts.append(
                    "The selected newsletter-specific Resend API key "
                    f"(id={newsletter.resend_api_key_id}) no longer exists."
                )
            elif stored_key.provider_type != "resend":
                logger.warning(
                    "Newsletter id=%s references non-Resend API key id=%s provider_type=%s",
                    newsletter.id,
                    stored_key.id,
                    stored_key.provider_type,
                )
                detail_parts.append(
                    "The selected newsletter-specific API key "
                    f"'{stored_key.name}' (id={stored_key.id}) is for provider "
                    f"'{stored_key.provider_type}', not 'resend'."
                )
            elif not stored_key.is_active:
                logger.info(
                    "Newsletter id=%s selected inactive Resend API key id=%s",
                    newsletter.id,
                    stored_key.id,
                )
                detail_parts.append(
                    "The selected newsletter-specific Resend API key "
                    f"'{stored_key.name}' (id={stored_key.id}) is inactive."
                )
            else:
                try:
                    decrypted_key = _normalize_config_value(decrypt_secret(stored_key.key_value))
                except Exception as exc:
                    logger.warning(
                        "Failed to decrypt newsletter Resend API key id=%s "
                        "for newsletter id=%s: %s",
                        stored_key.id,
                        newsletter.id,
                        exc,
                    )
                    detail_parts.append(
                        "The selected newsletter-specific Resend API key "
                        f"'{stored_key.name}' (id={stored_key.id}) could not be "
                        "decrypted. Re-save the key and try again."
                    )
                else:
                    if decrypted_key:
                        from_email = _normalize_config_value(
                            _get_resend_from_email(
                                settings,
                                newsletter,
                                api_key_record=stored_key,
                            )
                        )
                        detail = (
                            f"Using newsletter-specific Resend API key '{stored_key.name}' "
                            f"(id={stored_key.id})."
                        )
                        if from_email:
                            detail = f"{detail} Using sender '{from_email}'."
                        else:
                            detail = (
                                f"{detail} No sender email configured — "
                                "set a Sender Email on this API key in Settings > API Keys."
                            )
                        logger.debug(
                            "Using newsletter-specific Resend API key id=%s for newsletter id=%s",
                            stored_key.id,
                            newsletter.id,
                        )
                        return ResendConfigurationResolution(
                            api_key=decrypted_key,
                            from_email=from_email,
                            api_key_source="newsletter",
                            detail=detail,
                        )
                    detail_parts.append(
                        "The selected newsletter-specific Resend API key "
                        f"'{stored_key.name}' (id={stored_key.id}) is empty."
                    )

        from_email = _normalize_config_value(_get_resend_from_email(settings, newsletter))
        if from_email:
            detail_parts.append(f"Using sender '{from_email}'.")
        else:
            detail_parts.append(
                "No sender email is configured for the selected newsletter-specific Resend key, "
                "and PULSE_NEWS_RESEND_FROM_EMAIL is not set."
            )
        detail = " ".join(detail_parts)
        logger.info(
            "Newsletter-specific Resend configuration is unusable for newsletter id=%s: %s",
            newsletter.id,
            detail,
        )
        return ResendConfigurationResolution(
            api_key=None,
            from_email=from_email,
            api_key_source="newsletter",
            detail=detail,
        )

    detail_parts: list[str] = []
    if newsletter:
        detail_parts.append("No newsletter-specific Resend API key is selected.")

    env_api_key = _normalize_config_value(settings.resend_api_key)
    env_from_email = _normalize_config_value(_get_resend_from_email(settings, newsletter))
    if env_api_key and env_from_email:
        detail = " ".join([*detail_parts, "Using PULSE_NEWS_RESEND_API_KEY."])
        detail = f"{detail} Using sender '{env_from_email}'."
        return ResendConfigurationResolution(
            api_key=env_api_key,
            from_email=env_from_email,
            api_key_source="environment",
            detail=detail,
        )

    if env_api_key:
        detail_parts.append(
            "PULSE_NEWS_RESEND_API_KEY is set, but PULSE_NEWS_RESEND_FROM_EMAIL is not set."
        )
    else:
        detail_parts.append("PULSE_NEWS_RESEND_API_KEY is not set.")

    if env_from_email:
        detail_parts.append(f"Using sender '{env_from_email}'.")
    else:
        detail_parts.append("PULSE_NEWS_RESEND_FROM_EMAIL is not set.")

    detail = " ".join(detail_parts)
    logger.info(
        "No usable Resend API key resolved for newsletter id=%s: %s",
        newsletter.id if newsletter else None,
        detail,
    )
    return ResendConfigurationResolution(
        api_key=None,
        from_email=env_from_email,
        api_key_source="missing",
        detail=detail,
    )


def _get_resend_api_key(
    settings: Settings,
    newsletter: Newsletter | None = None,
    *,
    db_session=None,
) -> str | None:
    return _resolve_resend_configuration(
        settings,
        newsletter,
        db_session=db_session,
    ).api_key


def _get_resend_from_email(
    settings: Settings,
    newsletter: Newsletter | None = None,
    *,
    api_key_record: ApiKey | None = None,
) -> str | None:
    if api_key_record and api_key_record.from_email:
        return _normalize_config_value(api_key_record.from_email)
    return settings.resend_from_email


def _resend_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Pulse-News/1.0",
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

    max_attempts = 3
    for attempt_number in range(1, max_attempts + 1):
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
            detail = _decode_http_error_detail(exc)
            if exc.code in (429, 502, 503, 504) and attempt_number < max_attempts:
                backoff = min(attempt_number * 2, 10)
                logger.info(
                    "Resend retryable error (%d) for %s, retrying in %ds (attempt %d/%d)",
                    exc.code,
                    target.email,
                    backoff,
                    attempt_number,
                    max_attempts,
                )
                time.sleep(backoff)
                continue
            return _failed_outcome(
                email=target.email,
                detail=f"Resend HTTP error: {detail}",
            )
        except error.URLError as exc:
            return _failed_outcome(
                email=target.email,
                detail=f"Resend connection error: {exc.reason}",
            )

    return _failed_outcome(
        email=target.email,
        detail="Resend delivery exhausted all retry attempts.",
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
            if exc.code in (429, 502, 503, 504) and attempt_number < RESEND_BATCH_MAX_ATTEMPTS:
                backoff = min(attempt_number * 2, 10)
                logger.info(
                    "Resend batch retryable error (%d) for chunk %d, "
                    "retrying in %ds (attempt %d/%d)",
                    exc.code,
                    chunk_index,
                    backoff,
                    attempt_number,
                    RESEND_BATCH_MAX_ATTEMPTS,
                )
                time.sleep(backoff)
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
    db_session=None,
) -> TestSendResult:
    resend_configuration = _resolve_resend_configuration(
        settings,
        newsletter,
        db_session=db_session,
    )
    api_key = resend_configuration.api_key
    from_email = resend_configuration.from_email

    if not api_key or not from_email:
        missing_parts = []
        if not api_key:
            missing_parts.append("Resend API key")
        if not from_email:
            missing_parts.append("sender email address")
        missing_str = " and ".join(missing_parts)

        if settings.environment == "production":
            raise RuntimeError(
                f"Cannot test-send in production without {missing_str}. "
                f"{resend_configuration.detail}"
            )
        if settings.allow_simulated_email_delivery:
            logger.info(
                "Returning explicit local preview test-send result for %s: missing %s. Detail: %s",
                to_email,
                missing_str,
                resend_configuration.detail,
            )
            return TestSendResult(
                status="simulated",
                mode="local-preview",
                message=(
                    f"Email delivery simulation is enabled via "
                    f"{SIMULATED_EMAIL_DELIVERY_ENV_VAR}=true. Missing {missing_str}. "
                    f"{resend_configuration.detail} No email was sent."
                ),
                provider_id=None,
                to_email=to_email,
            )
        return TestSendResult(
            status="error",
            mode="none",
            message=(
                f"Resend test send is blocked: missing {missing_str}. "
                f"{resend_configuration.detail} Configure a valid newsletter-specific Resend key, "
                "or set both PULSE_NEWS_RESEND_API_KEY and PULSE_NEWS_RESEND_FROM_EMAIL. "
                "For non-production local preview only, set "
                f"{SIMULATED_EMAIL_DELIVERY_ENV_VAR}=true."
            ),
            provider_id=None,
            to_email=to_email,
        )

    logger.info(
        "Sending Resend test email to %s using %s configuration",
        to_email,
        resend_configuration.api_key_source,
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
        detail = _decode_http_error_detail(exc)
        logger.warning(
            "Resend test send HTTP error for %s using %s configuration: %s",
            to_email,
            resend_configuration.api_key_source,
            detail,
        )
        raise RuntimeError(
            f"Resend test send failed. {resend_configuration.detail} Provider response: {detail}"
        ) from exc
    except error.URLError as exc:
        logger.warning(
            "Resend test send connection error for %s using %s configuration: %s",
            to_email,
            resend_configuration.api_key_source,
            exc.reason,
        )
        raise RuntimeError(
            f"Resend test send failed. {resend_configuration.detail} Connection error: {exc.reason}"
        ) from exc

    return TestSendResult(
        status="sent",
        mode="resend",
        message=(f"Test email sent successfully through Resend. {resend_configuration.detail}"),
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
    db_session=None,
) -> ManualSendResult:
    resend_configuration = _resolve_resend_configuration(
        settings,
        newsletter,
        db_session=db_session,
    )
    api_key = resend_configuration.api_key
    from_email = resend_configuration.from_email

    if settings.environment == "production" and (not api_key or not from_email):
        missing_parts = []
        if not api_key:
            missing_parts.append("Resend API key")
        if not from_email:
            missing_parts.append("sender email address")
        missing_str = " and ".join(missing_parts)
        raise RuntimeError(
            f"Cannot send emails in production without {missing_str}. {resend_configuration.detail}"
        )

    if not api_key or not from_email:
        missing_parts = []
        if not api_key:
            missing_parts.append("Resend API key")
        if not from_email:
            missing_parts.append("sender email address")
        missing_str = " and ".join(missing_parts)
        if settings.allow_simulated_email_delivery:
            logger.info(
                "Returning explicit local preview delivery for newsletter id=%s: "
                "missing %s. Detail: %s",
                newsletter.id if newsletter else None,
                missing_str,
                resend_configuration.detail,
            )
            return ManualSendResult(
                status="fallback",
                mode="local-preview",
                message=(
                    f"Email delivery simulation is enabled via "
                    f"{SIMULATED_EMAIL_DELIVERY_ENV_VAR}=true. Missing {missing_str}. "
                    f"{resend_configuration.detail} No email was sent."
                ),
                recipient_outcomes=[
                    RecipientSendOutcome(
                        email=target.email,
                        status="simulated",
                        provider_id=None,
                        detail=(
                            "Local preview simulation enabled via "
                            f"{SIMULATED_EMAIL_DELIVERY_ENV_VAR}=true"
                        ),
                    )
                    for target in recipient_targets
                ],
            )
        return ManualSendResult(
            status="failed",
            mode="none",
            message=(
                f"Resend delivery is blocked: missing {missing_str}. "
                f"{resend_configuration.detail} Configure a valid newsletter-specific Resend key, "
                "or set both PULSE_NEWS_RESEND_API_KEY and PULSE_NEWS_RESEND_FROM_EMAIL. "
                "For non-production local preview only, set "
                f"{SIMULATED_EMAIL_DELIVERY_ENV_VAR}=true."
            ),
            recipient_outcomes=[
                RecipientSendOutcome(
                    email=target.email,
                    status="failed",
                    provider_id=None,
                    detail=f"Delivery blocked: missing {missing_str}.",
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
        message = (
            f"Delivered to all active recipients through Resend. {resend_configuration.detail}"
        )
    elif any(item.status == "sent" for item in outcomes):
        overall_status = "partial"
        message = (
            "Delivered to some active recipients, but one or more deliveries failed. "
            f"{resend_configuration.detail}"
        )
    else:
        overall_status = "failed"
        message = f"Delivery failed for every active recipient. {resend_configuration.detail}"

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
    db_session=None,
) -> ReconciliationEvent:
    if current_mode != "resend" or not provider_id:
        return ReconciliationEvent(
            event_status="simulated",
            message="No live provider status is available for this delivery outcome.",
            provider_id=provider_id,
        )

    resend_configuration = _resolve_resend_configuration(
        settings,
        newsletter,
        db_session=db_session,
    )
    api_key = resend_configuration.api_key
    if not api_key:
        return ReconciliationEvent(
            event_status="unknown",
            message=f"Cannot retrieve status without Resend API key. {resend_configuration.detail}",
            provider_id=provider_id,
        )

    retrieve_request = request.Request(
        f"{settings.resend_api_base_url}/emails/{provider_id}",
        headers=_resend_headers(api_key),
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
