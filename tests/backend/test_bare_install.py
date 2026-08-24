"""The bare-install leg's own assertions (docs/CONTRACT.md §9's two-leg test strategy).

Two things this file proves that nothing else in the suite does:

  1. **No stray top-level extra import** — meaningful in BOTH legs. In the gate leg (extras
     installed) this catches a top-level `import cryptography`/`import PIL` slipping into
     `appkit.crypto`/`appkit.files` that would make an "optional" extra mandatory in practice
     despite `pyproject.toml` saying otherwise. Run as a subprocess: pytest plugins and Django
     itself import all sorts of things incidentally in-process, so only a fresh interpreter
     gives a clean answer.
  2. **The missing-extra `ImportError` message is the actionable one** — genuinely bare-only
     (skipped when the extra IS installed, since there's nothing to test): appkit.crypto/
     appkit.files import cleanly with neither extra present (module-level import never touches
     `cryptography`/`PIL`), and the *usage* path (`Cipher(...)`/dimension-checked
     `validate_image(...)`) raises `ImportError` naming the install fix — not a bare
     `ModuleNotFoundError` three frames deep. The *simulated*-absence versions of this same
     assertion (`monkeypatch.setitem(sys.modules, ..., None)`) live in `test_crypto.py` and
     `test_files.py`, and cover the same `raise` branches in both legs.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"

_NO_STRAY_IMPORT_PROBE = """
import sys
import appkit.crypto
import appkit.files
assert "cryptography" not in sys.modules, (
    "importing appkit.crypto/appkit.files pulled in 'cryptography' at module scope"
)
assert "PIL" not in sys.modules, (
    "importing appkit.crypto/appkit.files pulled in 'PIL' at module scope"
)
print("OK")
"""


def test_importing_crypto_and_files_never_imports_their_extras_at_module_scope() -> None:
    """Meaningful in both test legs (see module docstring, point 1)."""
    result = subprocess.run(
        [sys.executable, "-c", _NO_STRAY_IMPORT_PROBE],
        capture_output=True,
        text=True,
        cwd=BACKEND_DIR,
        env={**os.environ, "PYTHONPATH": str(BACKEND_DIR / "src")},
    )
    assert result.returncode == 0, f"probe failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    assert result.stdout.strip() == "OK"


@pytest.mark.skipif(
    importlib.util.find_spec("cryptography") is not None,
    reason="only meaningful when 'cryptography' is genuinely absent (the bare-install leg)",
)
def test_missing_crypto_extra_message_is_actionable() -> None:
    from appkit.crypto import Cipher, generate_key

    for call in (lambda: generate_key(), lambda: Cipher("not-checked-before-import")):
        with pytest.raises(ImportError, match=r"appkit\[crypto\]"):
            call()


@pytest.mark.skipif(
    importlib.util.find_spec("PIL") is not None,
    reason="only meaningful when 'PIL' is genuinely absent (the bare-install leg)",
)
def test_missing_images_extra_message_is_actionable(tmp_path: object) -> None:
    from django.core.files.uploadedfile import SimpleUploadedFile

    from appkit.files import validate_image

    png_header = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    upload = SimpleUploadedFile("x.png", png_header, content_type="image/png")
    with pytest.raises(ImportError, match=r"appkit\[images\]"):
        validate_image(upload)
