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
    with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
        response = client.post(
            DEVICE_USERCODE_URL,
            json={"client_id": CLIENT_ID, "scope": SCOPE},
        )
    if response.status_code not in (200, 201):
        raise OpenAIOAuthError(
            f"Device-code init failed ({response.status_code}): {response.text[:200]}",
            status_code=response.status_code,
        )
    data = response.json()
    return DeviceCodeInit(
        device_auth_id=data["device_auth_id"],
        user_code=data["user_code"],
        interval=int(data.get("interval", 5)),
        expires_in=int(data.get("expires_in", 900)),
        verification_uri=data.get("verification_uri", "https://auth.openai.com/codex/device"),
    )


def device_code_poll(device_auth_id: str, user_code: str) -> TokenBundle | None:
    """Poll for device-code completion.

    Returns None while authorization is still pending.
    Raises OpenAIOAuthError on hard failures (expired, denied, network).
    On success, exchanges the returned authorization_code and returns a
    TokenBundle.
    """
    with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
        response = client.post(
            DEVICE_TOKEN_URL,
            json={
                "client_id": CLIENT_ID,
                "device_auth_id": device_auth_id,
                "user_code": user_code,
            },
        )

    if response.status_code == 202:
        # Still pending — caller should poll again after interval.
        return None

    if response.status_code not in (200, 201):
        body = response.text[:200]
        # Retryable "still waiting" states — OpenAI returns these while the
        # user has not yet completed device authorization.
        if response.status_code == 400 and "authorization_pending" in body:
            return None
        if response.status_code == 403 and "deviceauth_authorization_unknown" in body:
            return None
        raise OpenAIOAuthError(
            f"Device-code poll failed ({response.status_code}): {body}",
            status_code=response.status_code,
        )

    data = response.json()
    # Device-code endpoint returns an authorization_code + server-generated verifier.
    authorization_code = data.get("authorization_code") or data.get("code")
    server_verifier = data.get("code_verifier") or data.get("verifier") or ""

    if not authorization_code:
        # Some implementations return tokens directly without a code exchange.
        if "access_token" in data:
            return _build_bundle_from_token_response(data)
        raise OpenAIOAuthError(
            f"Device-code poll succeeded but no authorization_code in response: {data}"
        )

    return _exchange_code_internal(
        code=authorization_code,
        verifier=server_verifier,
        redirect_uri=DEVICE_CODE_REDIRECT_URI,
    )


def exchange_code(code: str, verifier: str, redirect_uri: str) -> TokenBundle:
    """Exchange a loopback authorization code for tokens (PKCE)."""
    return _exchange_code_internal(code=code, verifier=verifier, redirect_uri=redirect_uri)


def _exchange_code_internal(code: str, verifier: str, redirect_uri: str) -> TokenBundle:
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
    if response.status_code not in (200, 201):
        raise OpenAIOAuthError(
            f"Token exchange failed ({response.status_code}): {response.text[:200]}",
            status_code=response.status_code,
        )
    return _build_bundle_from_token_response(response.json())


def refresh(refresh_token_value: str) -> TokenBundle:
    """Exchange a refresh token for a new access token.

    If the upstream response omits ``refresh_token``, we keep the one the
    caller supplied so the stored value isn't wiped out — otherwise the
    next refresh would send an empty token and the session would become
    unrecoverable.
    """
    with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
        response = client.post(
            TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token_value,
            },
        )
    if response.status_code not in (200, 201):
        raise OpenAIOAuthError(
            f"Token refresh failed ({response.status_code}): {response.text[:200]}",
            status_code=response.status_code,
        )
    return _build_bundle_from_token_response(
        response.json(), fallback_refresh_token=refresh_token_value
    )


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
    access_token = data["access_token"]
    # OAuth refresh responses may omit refresh_token — in that case, keep the
    # one the caller already has so we don't blow away a still-valid token.
    refresh_token_value = data.get("refresh_token") or fallback_refresh_token or ""

    # Always use the upstream expires_at / expires_in value — never derive
    # from now() to avoid drift.
    if "expires_at" in data:
        expires_at = datetime.fromtimestamp(int(data["expires_at"]), tz=UTC)
    else:
        expires_in = int(data.get("expires_in", 3600))
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

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
