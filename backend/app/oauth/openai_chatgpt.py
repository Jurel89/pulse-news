"""OpenAI ChatGPT OAuth helpers (device-code flow + token lifecycle).

Uses the same public client_id that the open-source Codex CLI uses, so
device-code pages render correctly with OpenAI's own branding.  No
signature verification on JWT payloads — OpenAI rotates keys arbitrarily
and the tokens are opaque to us; we only need the claim values.

All HTTP via a synchronous httpx.Client because FastAPI route handlers that
call this module are normal (non-async) functions.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — values from github.com/openai/codex codex-rs/login/
# ---------------------------------------------------------------------------

CLIENT_ID = os.environ.get(
    "PULSE_NEWS_OPENAI_CHATGPT_CLIENT_ID",
    "app_EMoamEEZ73f0CkXaXp7hrann",
)

# Supported models for ChatGPT subscription generation.
# Used for validation at provider/newsletter save time and runtime.
CHATGPT_SUPPORTED_MODELS = ("gpt-5.4", "gpt-5.4-mini", "gpt-5.2")
CHATGPT_DEFAULT_MODEL = "gpt-5.4"

AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
LOOPBACK_REDIRECT_URI = "http://localhost:1455/auth/callback"
DEVICE_CODE_REDIRECT_URI = "https://auth.openai.com/deviceauth/callback"
DEVICE_USERCODE_URL = "https://auth.openai.com/api/accounts/deviceauth/usercode"
DEVICE_TOKEN_URL = "https://auth.openai.com/api/accounts/deviceauth/token"
SCOPE = "openid profile email offline_access"
ORIGINATOR = "codex_cli_rs"

_HTTP_TIMEOUT = httpx.Timeout(30.0)


# ---------------------------------------------------------------------------
# Typed results
# ---------------------------------------------------------------------------


@dataclass
class TokenBundle:
    """Token bundle returned from any successful OAuth exchange or refresh."""

    access_token: str
    refresh_token: str
    # Always populated from the upstream response field, never derived from now().
    expires_at: datetime
    account_id: str | None
    plan_type: str | None
    id_token: str | None


@dataclass
class DeviceCodeInit:
    device_auth_id: str
    user_code: str
    interval: int
    expires_in: int
    verification_uri: str


class OpenAIOAuthError(Exception):
    """Raised when an upstream OAuth call returns an error status."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# PKCE
# ---------------------------------------------------------------------------


def generate_pkce() -> tuple[str, str]:
    """Return (verifier, challenge) pair.

    Verifier: URL-safe base64 of 32 random bytes, no padding.
    Challenge: URL-safe base64 of SHA-256(verifier), no padding.
    """
    raw = secrets.token_bytes(32)
    verifier = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    challenge_bytes = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(challenge_bytes).rstrip(b"=").decode("ascii")
    return verifier, challenge


def build_authorize_url(state: str, challenge: str, redirect_uri: str) -> str:
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": SCOPE,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "originator": ORIGINATOR,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Device-code flow
# ---------------------------------------------------------------------------


def device_code_start() -> DeviceCodeInit:
    """Initiate a device-code flow.  Returns the user-code to display."""
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            response = client.post(
                DEVICE_USERCODE_URL,
                json={"client_id": CLIENT_ID, "scope": SCOPE},
            )
    except httpx.HTTPError as exc:
        raise OpenAIOAuthError(f"Device-code init network error: {exc}") from exc
    if response.status_code not in (200, 201):
        raise OpenAIOAuthError(
            f"Device-code init failed ({response.status_code}): {response.text[:200]}",
            status_code=response.status_code,
        )
    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise OpenAIOAuthError(f"Device-code init returned invalid JSON: {exc}") from exc
    try:
        interval = int(data.get("interval", 5))
        if "expires_in" in data:
            expires_in = int(data["expires_in"])
        elif "expires_at" in data:
            raw_expires = data["expires_at"]
            try:
                # OpenAI may return expires_at as a Unix timestamp integer.
                expires_at_ts = int(raw_expires)
            except ValueError:
                # Or as an ISO 8601 datetime string (observed in live responses).
                expires_at_dt = datetime.fromisoformat(raw_expires)
                if expires_at_dt.tzinfo is None:
                    expires_at_dt = expires_at_dt.replace(tzinfo=UTC)
                expires_at_ts = int(expires_at_dt.timestamp())
            expires_in = max(0, expires_at_ts - int(datetime.now(UTC).timestamp()))
        else:
            expires_in = 900
        return DeviceCodeInit(
            device_auth_id=data["device_auth_id"],
            user_code=data["user_code"],
            interval=interval,
            expires_in=expires_in,
            verification_uri=data.get("verification_uri", "https://auth.openai.com/codex/device"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise OpenAIOAuthError(f"Device-code init response malformed: {exc}") from exc


def device_code_poll(device_auth_id: str, user_code: str) -> tuple[TokenBundle | None, int | None]:
    """Poll for device-code completion.

    Returns (None, retry_after) while authorization is still pending.
    retry_after is the seconds to wait before the next poll (from OpenAI's
    slow_down or interval response).  None means "use the default interval".
    Raises OpenAIOAuthError on hard failures (expired, denied, network).
    On success, returns (TokenBundle, None).
    """
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            response = client.post(
                DEVICE_TOKEN_URL,
                json={
                    "client_id": CLIENT_ID,
                    "device_auth_id": device_auth_id,
                    "user_code": user_code,
                },
            )
    except httpx.HTTPError as exc:
        raise OpenAIOAuthError(f"Device-code poll network error: {exc}") from exc

    if response.status_code == 202:
        return None, None

    if response.status_code in (200, 201):
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise OpenAIOAuthError(f"Device-code poll returned invalid JSON: {exc}") from exc
        try:
            authorization_code = data.get("authorization_code") or data.get("code")
            server_verifier = data.get("code_verifier") or data.get("verifier") or ""
            if not authorization_code:
                if "access_token" in data:
                    return _build_bundle_from_token_response(data), None
                raise OpenAIOAuthError(
                    f"Device-code poll succeeded but no authorization_code in response: {data}"
                )
            return _exchange_code_internal(
                code=authorization_code,
                verifier=server_verifier,
                redirect_uri=DEVICE_CODE_REDIRECT_URI,
            ), None
        except OpenAIOAuthError:
            raise
        except (TypeError, AttributeError) as exc:
            raise OpenAIOAuthError(f"Device-code poll response malformed: {exc}") from exc

    is_pending, retry_after = _parse_poll_error(response)
    if is_pending:
        return None, retry_after

    body = response.text[:200]
    raise OpenAIOAuthError(
        f"Device-code poll failed ({response.status_code}): {body}",
        status_code=response.status_code,
    )


def _parse_poll_error(response: httpx.Response) -> tuple[bool, int | None]:
    """Return (is_pending, retry_after_seconds) from a non-2xx poll response.

    OpenAI returns various retryable states while the user has not yet
    completed device authorization. We check the JSON error payload for:

    - error: "authorization_pending" | "slow_down" | "deviceauth_authorization_unknown"
    - error.code: same values (nested shape)
    - error_description / error.message: "Device authorization is unknown"

    All of these mean "keep polling".
    """
    raw = response.text[:500]
    retry_after: int | None = None
    try:
        data = response.json()
    except Exception:
        data = {}

    error_str = ""
    error_code = ""
    error_msg = ""
    error_desc = ""

    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, str):
            error_str = err
        elif isinstance(err, dict):
            error_code = err.get("code") or ""
            error_msg = err.get("message") or ""
        error_desc = data.get("error_description") or ""
        raw_interval = data.get("interval")
        if isinstance(raw_interval, int):
            retry_after = raw_interval

    pending_codes = {"authorization_pending", "slow_down", "deviceauth_authorization_unknown"}
    for candidate in (error_str, error_code):
        if candidate in pending_codes:
            return True, retry_after

    for text in (error_msg, error_desc, raw):
        if "device authorization is unknown" in text.lower():
            return True, retry_after

    return False, retry_after


def exchange_code(code: str, verifier: str, redirect_uri: str) -> TokenBundle:
    """Exchange a loopback authorization code for tokens (PKCE)."""
    return _exchange_code_internal(code=code, verifier=verifier, redirect_uri=redirect_uri)


def _exchange_code_internal(code: str, verifier: str, redirect_uri: str) -> TokenBundle:
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            response = client.post(
                TOKEN_URL,
                data={
                    "client_id": CLIENT_ID,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "code_verifier": verifier,
                },
            )
    except httpx.HTTPError as exc:
        raise OpenAIOAuthError(f"Token exchange network error: {exc}") from exc
    if response.status_code not in (200, 201):
        raise OpenAIOAuthError(
            f"Token exchange failed ({response.status_code}): {response.text[:200]}",
            status_code=response.status_code,
        )
    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise OpenAIOAuthError(f"Token exchange returned invalid JSON: {exc}") from exc
    return _build_bundle_from_token_response(data)


def refresh(refresh_token_value: str) -> TokenBundle:
    """Exchange a refresh token for a new access token.

    If the upstream response omits ``refresh_token``, we keep the one the
    caller supplied so the stored value isn't wiped out — otherwise the
    next refresh would send an empty token and the session would become
    unrecoverable.
    """
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            response = client.post(
                TOKEN_URL,
                data={
                    "client_id": CLIENT_ID,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token_value,
                },
            )
    except httpx.HTTPError as exc:
        raise OpenAIOAuthError(f"Token refresh network error: {exc}") from exc
    if response.status_code not in (200, 201):
        raise OpenAIOAuthError(
            f"Token refresh failed ({response.status_code}): {response.text[:200]}",
            status_code=response.status_code,
        )
    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise OpenAIOAuthError(f"Token refresh returned invalid JSON: {exc}") from exc
    return _build_bundle_from_token_response(data, fallback_refresh_token=refresh_token_value)


# ---------------------------------------------------------------------------
# JWT parsing (no signature verification)
# ---------------------------------------------------------------------------


def parse_jwt_payload(token: str) -> dict[str, Any]:
    """Decode the JWT payload segment.  Does NOT verify signature."""
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Not a valid JWT (fewer than 2 segments).")
    # Add padding back before decoding
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded)
        return json.loads(decoded)
    except Exception as exc:
        raise ValueError(f"JWT payload could not be decoded: {exc}") from exc


def extract_account_id(payload: dict[str, Any]) -> str | None:
    """Extract chatgpt_account_id from JWT payload."""
    auth_ns = payload.get("https://api.openai.com/auth", {})
    return auth_ns.get("chatgpt_account_id")


def extract_plan_type(payload: dict[str, Any]) -> str | None:
    """Extract chatgpt_plan_type from JWT payload."""
    auth_ns = payload.get("https://api.openai.com/auth", {})
    return auth_ns.get("chatgpt_plan_type")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_bundle_from_token_response(
    data: dict[str, Any],
    *,
    fallback_refresh_token: str | None = None,
) -> TokenBundle:
    try:
        access_token = data["access_token"]
    except KeyError as exc:
        raise OpenAIOAuthError(f"Token response missing required field: {exc}") from exc
    # OAuth refresh responses may omit refresh_token — in that case, keep the
    # one the caller already has so we don't blow away a still-valid token.
    # Initial materialization (exchange_code, device_code) must have a refresh_token.
    refresh_token_value = data.get("refresh_token") or fallback_refresh_token
    if refresh_token_value is None:
        raise OpenAIOAuthError(
            "Token response missing refresh_token. "
            "Initial OAuth exchange must include a refresh token."
        )

    # Always use the upstream expires_at / expires_in value — never derive
    # from now() to avoid drift.
    try:
        if "expires_at" in data:
            expires_at = datetime.fromtimestamp(int(data["expires_at"]), tz=UTC)
        else:
            expires_in = int(data.get("expires_in", 3600))
            expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    except (TypeError, ValueError) as exc:
        raise OpenAIOAuthError(f"Token response has invalid expiry: {exc}") from exc

    account_id: str | None = None
    plan_type: str | None = None
    try:
        payload = parse_jwt_payload(access_token)
        account_id = extract_account_id(payload)
        plan_type = extract_plan_type(payload)
    except Exception:
        logger.debug(
            "Could not parse JWT claims from access token; leaving account_id/plan_type blank."
        )

    return TokenBundle(
        access_token=access_token,
        refresh_token=refresh_token_value,
        expires_at=expires_at,
        account_id=account_id,
        plan_type=plan_type,
        id_token=data.get("id_token"),
    )
