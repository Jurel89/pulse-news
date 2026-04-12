from __future__ import annotations

import base64
import ctypes
import ctypes.util
import hashlib
import os
from functools import lru_cache

import app.config as config

_ENCRYPTED_PREFIX = "enc:v1:"
_KDF_SALT = b"pulse-news:api-key-encryption:v1"
_PBKDF2_ITERATIONS = 200_000
_KEY_LENGTH = 32
_NONCE_LENGTH = 12
_TAG_LENGTH = 16
_EVP_CTRL_GCM_SET_IVLEN = 0x9
_EVP_CTRL_GCM_GET_TAG = 0x10
_EVP_CTRL_GCM_SET_TAG = 0x11


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("utf-8"))


def _require_success(result: int, message: str) -> None:
    if result != 1:
        raise ValueError(message)


def _bytes_buffer(value: bytes):
    buffer = (ctypes.c_ubyte * max(1, len(value)))()
    if value:
        ctypes.memmove(buffer, value, len(value))
    return buffer


@lru_cache(maxsize=1)
def _load_libcrypto() -> ctypes.CDLL:
    library_name = ctypes.util.find_library("crypto")
    if library_name is None:
        raise RuntimeError("OpenSSL libcrypto is required for secret encryption.")

    library = ctypes.CDLL(library_name)
    library.EVP_CIPHER_CTX_new.argtypes = []
    library.EVP_CIPHER_CTX_new.restype = ctypes.c_void_p
    library.EVP_CIPHER_CTX_free.argtypes = [ctypes.c_void_p]
    library.EVP_CIPHER_CTX_free.restype = None
    library.EVP_aes_256_gcm.argtypes = []
    library.EVP_aes_256_gcm.restype = ctypes.c_void_p
    library.EVP_EncryptInit_ex.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    library.EVP_EncryptInit_ex.restype = ctypes.c_int
    library.EVP_EncryptUpdate.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    library.EVP_EncryptUpdate.restype = ctypes.c_int
    library.EVP_EncryptFinal_ex.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int),
    ]
    library.EVP_EncryptFinal_ex.restype = ctypes.c_int
    library.EVP_DecryptInit_ex.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    library.EVP_DecryptInit_ex.restype = ctypes.c_int
    library.EVP_DecryptUpdate.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    library.EVP_DecryptUpdate.restype = ctypes.c_int
    library.EVP_DecryptFinal_ex.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int),
    ]
    library.EVP_DecryptFinal_ex.restype = ctypes.c_int
    library.EVP_CIPHER_CTX_ctrl.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
    ]
    library.EVP_CIPHER_CTX_ctrl.restype = ctypes.c_int
    return library


@lru_cache(maxsize=8)
def _derive_key(secret_key: str) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        secret_key.encode("utf-8"),
        _KDF_SALT,
        _PBKDF2_ITERATIONS,
        dklen=_KEY_LENGTH,
    )


def _encrypt_aes_gcm(plaintext: bytes, key: bytes, nonce: bytes) -> tuple[bytes, bytes]:
    library = _load_libcrypto()
    context = library.EVP_CIPHER_CTX_new()
    if not context:
        raise RuntimeError("OpenSSL cipher context could not be created.")

    key_buffer = _bytes_buffer(key)
    nonce_buffer = _bytes_buffer(nonce)
    plaintext_buffer = _bytes_buffer(plaintext)
    ciphertext_buffer = (ctypes.c_ubyte * max(1, len(plaintext) + _TAG_LENGTH))()
    tag_buffer = (ctypes.c_ubyte * _TAG_LENGTH)()

    try:
        cipher = library.EVP_aes_256_gcm()
        _require_success(
            library.EVP_EncryptInit_ex(context, cipher, None, None, None),
            "Secret encryption failed.",
        )
        _require_success(
            library.EVP_CIPHER_CTX_ctrl(context, _EVP_CTRL_GCM_SET_IVLEN, len(nonce), None),
            "Secret encryption failed.",
        )
        _require_success(
            library.EVP_EncryptInit_ex(
                context,
                None,
                None,
                ctypes.cast(key_buffer, ctypes.c_void_p),
                ctypes.cast(nonce_buffer, ctypes.c_void_p),
            ),
            "Secret encryption failed.",
        )

        output_length = ctypes.c_int(0)
        _require_success(
            library.EVP_EncryptUpdate(
                context,
                ctypes.cast(ciphertext_buffer, ctypes.c_void_p),
                ctypes.byref(output_length),
                ctypes.cast(plaintext_buffer, ctypes.c_void_p),
                len(plaintext),
            ),
            "Secret encryption failed.",
        )

        final_length = ctypes.c_int(0)
        _require_success(
            library.EVP_EncryptFinal_ex(
                context,
                ctypes.cast(ctypes.byref(ciphertext_buffer, output_length.value), ctypes.c_void_p),
                ctypes.byref(final_length),
            ),
            "Secret encryption failed.",
        )
        _require_success(
            library.EVP_CIPHER_CTX_ctrl(
                context,
                _EVP_CTRL_GCM_GET_TAG,
                _TAG_LENGTH,
                ctypes.cast(tag_buffer, ctypes.c_void_p),
            ),
            "Secret encryption failed.",
        )
    finally:
        library.EVP_CIPHER_CTX_free(context)

    total_length = output_length.value + final_length.value
    return bytes(ciphertext_buffer[:total_length]), bytes(tag_buffer[:_TAG_LENGTH])


def _decrypt_aes_gcm(ciphertext: bytes, key: bytes, nonce: bytes, tag: bytes) -> bytes:
    library = _load_libcrypto()
    context = library.EVP_CIPHER_CTX_new()
    if not context:
        raise RuntimeError("OpenSSL cipher context could not be created.")

    key_buffer = _bytes_buffer(key)
    nonce_buffer = _bytes_buffer(nonce)
    ciphertext_buffer = _bytes_buffer(ciphertext)
    tag_buffer = _bytes_buffer(tag)
    plaintext_buffer = (ctypes.c_ubyte * max(1, len(ciphertext) + _TAG_LENGTH))()

    try:
        cipher = library.EVP_aes_256_gcm()
        _require_success(
            library.EVP_DecryptInit_ex(context, cipher, None, None, None),
            "Encrypted secret could not be decrypted.",
        )
        _require_success(
            library.EVP_CIPHER_CTX_ctrl(context, _EVP_CTRL_GCM_SET_IVLEN, len(nonce), None),
            "Encrypted secret could not be decrypted.",
        )
        _require_success(
            library.EVP_DecryptInit_ex(
                context,
                None,
                None,
                ctypes.cast(key_buffer, ctypes.c_void_p),
                ctypes.cast(nonce_buffer, ctypes.c_void_p),
            ),
            "Encrypted secret could not be decrypted.",
        )

        output_length = ctypes.c_int(0)
        _require_success(
            library.EVP_DecryptUpdate(
                context,
                ctypes.cast(plaintext_buffer, ctypes.c_void_p),
                ctypes.byref(output_length),
                ctypes.cast(ciphertext_buffer, ctypes.c_void_p),
                len(ciphertext),
            ),
            "Encrypted secret could not be decrypted.",
        )
        _require_success(
            library.EVP_CIPHER_CTX_ctrl(
                context,
                _EVP_CTRL_GCM_SET_TAG,
                len(tag),
                ctypes.cast(tag_buffer, ctypes.c_void_p),
            ),
            "Encrypted secret could not be decrypted.",
        )

        final_length = ctypes.c_int(0)
        _require_success(
            library.EVP_DecryptFinal_ex(
                context,
                ctypes.cast(ctypes.byref(plaintext_buffer, output_length.value), ctypes.c_void_p),
                ctypes.byref(final_length),
            ),
            "Encrypted secret could not be decrypted.",
        )
    finally:
        library.EVP_CIPHER_CTX_free(context)

    total_length = output_length.value + final_length.value
    return bytes(plaintext_buffer[:total_length])


def is_encrypted(value: str) -> bool:
    return value.startswith(_ENCRYPTED_PREFIX)


def encrypt_secret(plaintext: str) -> str:
    key = _derive_key(config.get_settings().secret_key)
    nonce = os.urandom(_NONCE_LENGTH)
    ciphertext, tag = _encrypt_aes_gcm(plaintext.encode("utf-8"), key, nonce)
    return f"{_ENCRYPTED_PREFIX}{_b64encode(nonce)}:{_b64encode(ciphertext)}:{_b64encode(tag)}"


def decrypt_secret(ciphertext: str) -> str:
    if not is_encrypted(ciphertext):
        return ciphertext

    parts = ciphertext.split(":", maxsplit=4)
    if len(parts) != 5 or parts[0] != "enc" or parts[1] != "v1":
        raise ValueError("Encrypted secret could not be decrypted.")

    try:
        nonce = _b64decode(parts[2])
        encrypted_payload = _b64decode(parts[3])
        tag = _b64decode(parts[4])
    except Exception as exc:
        raise ValueError("Encrypted secret could not be decrypted.") from exc

    if len(nonce) != _NONCE_LENGTH or len(tag) != _TAG_LENGTH:
        raise ValueError("Encrypted secret could not be decrypted.")

    key = _derive_key(config.get_settings().secret_key)
    plaintext = _decrypt_aes_gcm(encrypted_payload, key, nonce, tag)
    try:
        return plaintext.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Encrypted secret could not be decrypted.") from exc
