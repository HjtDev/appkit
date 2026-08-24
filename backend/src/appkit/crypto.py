"""Fernet symmetric encryption primitive taking its key at construction time.

Requires the ``crypto`` extra (``appkit[crypto]``). A missing extra must fail with an
actionable message, never a bare ImportError — import ``cryptography`` lazily inside the
function/method that needs it, wrapped in try/except ImportError, re-raised naming the exact
fix (``Install with: uv add "appkit[crypto]"`` / ``pip install "appkit[crypto]"``). This error
path is itself unit-tested (docs/CONTRACT.md §9).

appkit never reads ``settings.FERNET_KEY`` or any other Django setting for this — the key is
always a call-time argument. This is the resolution to the tools/-vs-appkit tension
(docs/CONTRACT.md §3): field-level crypto stays in ``tools/crypto.py`` permanently, wrapping the
HOST's ``FERNET_KEY``; an app declaring ``appkit[crypto]`` builds a ``Cipher`` from its OWN
documented ``.env`` key. appkit therefore requires no ``.env`` key and no settings key for
encryption, under any install combination.

Public surface (docs/CONTRACT.md §2.5), implemented in a later phase:

    class Cipher:
        def __init__(self, key: str | bytes) -> None: ...   # raises ImproperlyConfigured on a
                                                              # bad key
        def encrypt(self, value: str) -> str: ...
        def decrypt(self, token: str) -> str: ...            # raises
                                                              # cryptography.fernet.InvalidToken

    def generate_key() -> str: ...
"""

from __future__ import annotations
