"""Fernet symmetric encryption primitive taking its key at construction time.

Requires the ``crypto`` extra (``hjtdev-appkit[crypto]``). A missing extra must fail with an
actionable message, never a bare ImportError — import ``cryptography`` lazily inside the
function/method that needs it, wrapped in try/except ImportError, re-raised naming the exact
fix (``Install with: uv add "hjtdev-appkit[crypto]"`` / ``pip install "hjtdev-appkit[crypto]"``).
This error path is itself unit-tested (docs/CONTRACT.md §9).

appkit never reads ``settings.FERNET_KEY`` or any other Django setting for this — the key is
always a call-time argument. This is the resolution to the tools/-vs-appkit tension
(docs/CONTRACT.md §3): field-level crypto stays in ``tools/crypto.py`` permanently, wrapping the
HOST's ``FERNET_KEY``; an app declaring ``hjtdev-appkit[crypto]`` builds a ``Cipher`` from its OWN
documented ``.env`` key. appkit therefore requires no ``.env`` key and no settings key for
encryption, under any install combination.

Public surface (docs/CONTRACT.md §2.5):

    class Cipher:
        def __init__(self, key: str | bytes) -> None: ...   # raises ImproperlyConfigured on a
                                                              # bad key
        def encrypt(self, value: str) -> str: ...
        def decrypt(self, token: str) -> str: ...            # raises
                                                              # cryptography.fernet.InvalidToken

    def generate_key() -> str: ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import ImproperlyConfigured

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

__all__ = ["Cipher", "generate_key"]

_INSTALL_HINT = (
    'Install with: uv add "hjtdev-appkit[crypto]" (or: pip install "hjtdev-appkit[crypto]")'
)


def _fernet_class() -> type[Fernet]:
    """Lazily imports `cryptography.fernet.Fernet`, behind the `crypto` extra.

    A missing extra must fail with an actionable message, never a bare `ImportError` three
    frames deep — this path is unit-tested by simulating the import failure.
    """
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise ImportError(
            f"appkit.crypto requires the 'cryptography' package. {_INSTALL_HINT}"
        ) from exc
    return Fernet


class Cipher:
    """Fernet symmetric encryption, keyed at construction — never from Django settings.

    A host's own encryption key is its own documented `.env` key; this class only ever wraps
    whatever key its caller passes in.
    """

    def __init__(self, key: str | bytes) -> None:
        """Builds the underlying `Fernet` cipher from `key`.

        Raises:
            ImportError: if the `crypto` extra isn't installed.
            ImproperlyConfigured: if `key` isn't a valid Fernet key (44-byte urlsafe-base64) —
                never the raw `cryptography` `ValueError`/`TypeError`/`binascii.Error` — naming
                `generate_key()` as the fix.
        """
        fernet_cls = _fernet_class()
        try:
            self._fernet = fernet_cls(key)
        except (TypeError, ValueError) as exc:
            raise ImproperlyConfigured(
                "appkit.crypto.Cipher() was given a key that is not a valid Fernet key. "
                "Generate one with appkit.crypto.generate_key()."
            ) from exc

    def encrypt(self, value: str) -> str:
        """Returns a URL-safe token string. Never raises for any `str` input."""
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, token: str) -> str:
        """Decrypts a token produced by `encrypt`.

        Raises `cryptography.fernet.InvalidToken` for a tampered, expired (if a TTL was used),
        or wrong-key token — never silently returns garbage.
        """
        return self._fernet.decrypt(token.encode()).decode()


def generate_key() -> str:
    """Thin wrapper over `Fernet.generate_key().decode()` — provisions a key for `Cipher`
    without a caller needing to `import cryptography` directly.
    """
    fernet_cls = _fernet_class()
    return fernet_cls.generate_key().decode()
