"""Encryption helpers for credentials stored in the application database."""

import os

from cryptography.fernet import Fernet, InvalidToken


class SecretStorageError(RuntimeError):
    """Raised when encrypted credentials cannot be safely stored or read."""


_PREFIX = "fernet:v1:"


def _fernet() -> Fernet:
    key = (os.getenv("LEETCODE_SESSION_ENCRYPTION_KEY") or "").strip()
    if not key:
        raise SecretStorageError(
            "LeetCode session storage is not configured. Set LEETCODE_SESSION_ENCRYPTION_KEY."
        )
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise SecretStorageError("LEETCODE_SESSION_ENCRYPTION_KEY is invalid.") from exc


def encrypt_leetcode_session(value: str) -> str:
    if not value:
        return ""
    return _PREFIX + _fernet().encrypt(value.encode()).decode()


def decrypt_leetcode_session(value: str) -> str:
    if not value:
        return ""
    # The field was reserved but unused before encrypted session storage was
    # introduced. Accept an existing unprefixed value as a legacy cookie and
    # let the caller re-encrypt it when the user saves settings.
    if not value.startswith(_PREFIX):
        return value
    try:
        return _fernet().decrypt(value[len(_PREFIX) :].encode()).decode()
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise SecretStorageError(
            "The saved LeetCode session cannot be decrypted. Reconnect LeetCode in settings."
        ) from exc
