from __future__ import annotations

import hashlib
import hmac
import os
from base64 import urlsafe_b64decode, urlsafe_b64encode


def _b64encode(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("utf-8")


def _b64decode(value: str) -> bytes:
    return urlsafe_b64decode(value.encode("utf-8"))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=64,
    )
    return f"scrypt$16384$8$1${_b64encode(salt)}${_b64encode(derived_key)}"


def verify_password(password: str, encoded_password: str) -> bool:
    algorithm, n_value, r_value, p_value, salt_value, key_value = encoded_password.split("$", maxsplit=5)
    if algorithm != "scrypt":
        return False

    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=_b64decode(salt_value),
        n=int(n_value),
        r=int(r_value),
        p=int(p_value),
        dklen=64,
    )
    return hmac.compare_digest(derived_key, _b64decode(key_value))
