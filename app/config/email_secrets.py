from __future__ import annotations

import base64
import os
from pathlib import Path

DEFAULT_KEY_FILE = Path("data/.email_settings_key")
ENCRYPTED_PREFIX = "enc:"


def _get_or_create_key(key_file: Path = DEFAULT_KEY_FILE) -> bytes:
    if key_file.exists():
        return key_file.read_bytes()

    key_file.parent.mkdir(parents=True, exist_ok=True)
    key = os.urandom(32)
    key_file.write_bytes(key)
    return key


def encrypt_secret(
    plain: str,
    *,
    key_file: Path = DEFAULT_KEY_FILE,
) -> str:
    if not plain:
        return ""

    key = _get_or_create_key(key_file)
    data = plain.encode("utf-8")
    encrypted = bytes(data[index] ^ key[index % len(key)] for index in range(len(data)))
    encoded = base64.urlsafe_b64encode(encrypted).decode("ascii")
    return f"{ENCRYPTED_PREFIX}{encoded}"


def decrypt_secret(
    stored: str,
    *,
    key_file: Path = DEFAULT_KEY_FILE,
) -> str:
    if not stored:
        return ""
    if not stored.startswith(ENCRYPTED_PREFIX):
        return ""

    if not key_file.exists():
        return ""

    key = key_file.read_bytes()
    encrypted = base64.urlsafe_b64decode(stored[len(ENCRYPTED_PREFIX) :])
    decrypted = bytes(
        encrypted[index] ^ key[index % len(key)] for index in range(len(encrypted))
    )
    return decrypted.decode("utf-8")
