"""`appkit.crypto` — Fernet encryption keyed at construction time (docs/CONTRACT.md §2.5).

Scaffold test coverage ports unchanged from `base-scaffold/backend/tools/tests/test_crypto.py`
— only the key's *source* changes, from `settings.FERNET_KEY` to a constructor argument.
"""

from __future__ import annotations

import sys

import pytest
from django.core.exceptions import ImproperlyConfigured

from appkit.crypto import Cipher, generate_key

# `cryptography.fernet` is imported lazily, INSIDE the `requires_extra`-marked tests that need
# it, not at module scope — a module-scope import here would make this whole file fail to
# *collect* on the bare-install leg (where `cryptography` genuinely isn't installed),
# defeating per-test `-m "not requires_extra"` deselection entirely.

# Only tests that actually exercise a real Fernet key need the extra installed — the simulated
# missing-extra test at the bottom deliberately carries no marker, so it runs (and matters) on
# both legs (docs/CONTRACT.md §9's two-leg strategy).
requires_extra = pytest.mark.requires_extra


@pytest.fixture
def key() -> str:
    return generate_key()


@requires_extra
def test_round_trip(key: str) -> None:
    cipher = Cipher(key)
    token = cipher.encrypt("hello world")
    assert cipher.decrypt(token) == "hello world"


@requires_extra
def test_ciphertext_differs_from_plaintext(key: str) -> None:
    cipher = Cipher(key)
    token = cipher.encrypt("hello world")
    assert token != "hello world"


@requires_extra
def test_two_encryptions_of_same_input_differ(key: str) -> None:
    # Fernet embeds a random IV and a timestamp, so encrypting the same plaintext twice must
    # never produce the same token — a repeat would be a real cryptographic bug.
    cipher = Cipher(key)
    first = cipher.encrypt("hello world")
    second = cipher.encrypt("hello world")
    assert first != second
    assert cipher.decrypt(first) == cipher.decrypt(second) == "hello world"


@requires_extra
def test_round_trip_non_ascii(key: str) -> None:
    cipher = Cipher(key)
    token = cipher.encrypt("héllo wörld — 你好")
    assert cipher.decrypt(token) == "héllo wörld — 你好"


@requires_extra
def test_tampered_token_is_rejected(key: str) -> None:
    from cryptography.fernet import InvalidToken

    cipher = Cipher(key)
    token = cipher.encrypt("hello world")
    tampered = token[:-4] + ("A" if token[-4] != "A" else "B") + token[-3:]
    with pytest.raises(InvalidToken):
        cipher.decrypt(tampered)


@requires_extra
def test_token_from_a_different_key_is_rejected(key: str) -> None:
    from cryptography.fernet import Fernet, InvalidToken

    cipher = Cipher(key)
    foreign_token = Fernet(Fernet.generate_key()).encrypt(b"hello world").decode()
    with pytest.raises(InvalidToken):
        cipher.decrypt(foreign_token)


@requires_extra
def test_invalid_key_raises_improperly_configured_naming_generate_key() -> None:
    with pytest.raises(ImproperlyConfigured, match="generate_key"):
        Cipher("not-a-valid-fernet-key")


@requires_extra
def test_generate_key_produces_a_usable_key() -> None:
    cipher = Cipher(generate_key())
    assert cipher.decrypt(cipher.encrypt("round trip")) == "round trip"


def test_missing_crypto_extra_raises_actionable_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simulates the `cryptography` package being absent — covers the same `raise` branch the
    genuinely-bare-install leg exercises in `test_bare_install.py`, but (deliberately unmarked)
    runs in both legs.
    """
    monkeypatch.setitem(sys.modules, "cryptography.fernet", None)
    with pytest.raises(ImportError, match=r"hjtdev-appkit\[crypto\]"):
        generate_key()
