"""A throwaway consumer field wrapping appkit.crypto.Cipher.

appkit ships NO Django model field and reads NO settings/.env key for encryption — the whole
point of docs/CONTRACT.md §3 is that a consuming app builds its own field on top of
appkit.crypto.Cipher(key), keyed from ITS OWN documented .env value (here, DEMO_FERNET_KEY,
config/settings.py). This module is the proof that the call-time-key boundary actually works
for a real Django field, not just a unit test constructing Cipher directly.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models

from appkit.crypto import Cipher


def _cipher() -> Cipher:
    key = getattr(settings, "DEMO_FERNET_KEY", "") or ""
    if not key:
        raise ValueError(
            "DEMO_FERNET_KEY is not set. This is demo/'s own .env key, never appkit's — "
            "generate one with `python -c \"from appkit.crypto import generate_key; "
            'print(generate_key())"`.'
        )
    return Cipher(key)


class EncryptedTextField(models.TextField):
    """Transparently encrypts on write, decrypts on read, via appkit.crypto.Cipher."""

    def from_db_value(self, value: Any, expression: Any, connection: Any) -> str | None:
        if value is None:
            return value
        return _cipher().decrypt(value)

    def get_prep_value(self, value: Any) -> str | None:
        if value is None:
            return value
        return _cipher().encrypt(str(value))
