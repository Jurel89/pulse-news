"""Create or reset an operator password.

Invoked by `make reset-password` inside the running container. Reads the target
email and new password from the RP_EMAIL and RP_PASSWORD environment variables
so neither value lands in the container process list.

Side effects:
- Creates the operator if it does not yet exist, or updates the password in place.
- Marks bootstrap as complete so the login form replaces the bootstrap form on
  the next page load.
"""

from __future__ import annotations

import os
import sys

from app.auth import normalize_email
from app.database import get_session_maker
from app.models import SystemSettings, User, utc_now
from app.security import hash_password


def main() -> int:
    email_raw = os.environ.get("RP_EMAIL")
    password = os.environ.get("RP_PASSWORD")
    if not email_raw or not password:
        print("RP_EMAIL and RP_PASSWORD must be set in the environment.", file=sys.stderr)
        return 1
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        return 1

    email = normalize_email(email_raw)
    session = get_session_maker()()
    try:
        user = session.query(User).filter(User.email == email).first()
        created = user is None
        if created:
            user = User(email=email, password_hash=hash_password(password))
            session.add(user)
        else:
            user.password_hash = hash_password(password)
        session.flush()

        settings = session.get(SystemSettings, 1)
        if settings is None:
            session.add(SystemSettings(id=1, initialized=True, bootstrap_disabled_at=utc_now()))
        elif not settings.initialized:
            settings.initialized = True
            settings.bootstrap_disabled_at = utc_now()

        session.commit()
    finally:
        session.close()

    action = "Created" if created else "Updated"
    print(f"{action} operator {email}. You can now log in with the new password.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
