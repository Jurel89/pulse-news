from __future__ import annotations

import hashlib


def build_delivery_attempt_key(
    *,
    newsletter_id: int,
    revision_id: int,
    trigger_mode: str,
    recipient_emails: list[str],
    fire_scope: str | None = None,
) -> str:
    normalized_recipients = ",".join(sorted(email.strip().lower() for email in recipient_emails))
    digest = hashlib.sha256(normalized_recipients.encode("utf-8")).hexdigest()[:16]
    scope = fire_scope or "default"
    return f"newsletter-{newsletter_id}-revision-{revision_id}-{trigger_mode}-{scope}-{digest}"
