from __future__ import annotations

import hashlib


def build_delivery_attempt_key(
    *,
    newsletter_id: int,
    revision_id: int,
    trigger_mode: str,
    recipient_emails: list[str],
) -> str:
    normalized_recipients = ",".join(sorted(email.strip().lower() for email in recipient_emails))
    digest = hashlib.sha256(normalized_recipients.encode("utf-8")).hexdigest()[:16]
    return f"newsletter-{newsletter_id}-revision-{revision_id}-{trigger_mode}-{digest}"
