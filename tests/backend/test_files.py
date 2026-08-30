"""`appkit.files` — magic-byte upload validation and image validation (docs/CONTRACT.md §2.9).

Image fixtures below are pre-generated, tiny, real PNG/JPEG bytes (base64-embedded) — this
file never imports `PIL` at module scope, since `validate_image` handles Pillow internally;
importing it here would fail collection on the bare-install leg.
"""

from __future__ import annotations

import base64
import sys

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from appkit.files import ImageInfo, detect_mimetype, validate_image, validate_upload

requires_extra = pytest.mark.requires_extra

# 4x3, solid red.
_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAQAAAADCAIAAAA7ljmRAAAAEElEQVR4nGP8z4AATAy4OAAmdgEF5PO41QAAAABJ"
    "RU5ErkJggg=="
)
# 4x3, same image, JPEG-encoded.
_JPEG_BYTES = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIs"
    "IxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMj"
    "IyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAADAAQDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAEC"
    "AwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2Jygg"
    "kKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZ"
    "mqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQ"
    "EBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKR"
    "obHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6go"
    "OEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3"
    "+Pn6/9oADAMBAAIRAxEAPwDi6KKK+ZP3E//Z"
)
# 50x40, solid green — bigger than the 4x3 default, for a dimension-limit test.
_BIG_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAADIAAAAoCAIAAAAzED4bAAAAQklEQVR4nO3OsQEAEADAMPz/Mw9YOjEkF2SOPT60"
    "XgfutAqtQqvQKrQKrUKr0Cq0Cq1Cq9AqtAqtQqvQKrQKrUKrOEdXAU8NmZPcAAAAAElFTkSuQmCC"
)

_SVG_BYTES = (
    b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="10" height="20"></svg>'
)
_SVG_BYTES_NO_PROLOG = b'<svg xmlns="http://www.w3.org/2000/svg" width="5" height="6"></svg>'


# ---------------------------------------------------------------- detect_mimetype


def test_detect_mimetype_identifies_png() -> None:
    assert detect_mimetype(_PNG_BYTES) == "image/png"


def test_detect_mimetype_identifies_jpeg() -> None:
    assert detect_mimetype(_JPEG_BYTES) == "image/jpeg"


def test_detect_mimetype_identifies_svg_with_prolog() -> None:
    assert detect_mimetype(_SVG_BYTES) == "image/svg+xml"


def test_detect_mimetype_identifies_svg_without_prolog() -> None:
    assert detect_mimetype(_SVG_BYTES_NO_PROLOG) == "image/svg+xml"


def test_detect_mimetype_returns_octet_stream_for_unrecognised_data() -> None:
    assert detect_mimetype(b"not a real file, just garbage bytes") == "application/octet-stream"


# ---------------------------------------------------------------- validate_upload


def test_validate_upload_accepts_an_allowed_mimetype() -> None:
    upload = SimpleUploadedFile("x.png", _PNG_BYTES, content_type="image/png")
    validate_upload(upload, allowed_mimetypes=["image/png"])  # does not raise


def test_validate_upload_rejects_a_disallowed_mimetype() -> None:
    upload = SimpleUploadedFile("x.jpg", _JPEG_BYTES, content_type="image/jpeg")
    with pytest.raises(ValidationError, match="image/jpeg"):
        validate_upload(upload, allowed_mimetypes=["image/png"])


def test_validate_upload_rejects_a_file_over_max_bytes() -> None:
    upload = SimpleUploadedFile("x.png", _PNG_BYTES, content_type="image/png")
    with pytest.raises(ValidationError, match="too large"):
        validate_upload(upload, allowed_mimetypes=["image/png"], max_bytes=10)


def test_validate_upload_rejects_extension_mimetype_disagreement() -> None:
    # Real PNG bytes, but a .txt name — extension disagrees with the detected type.
    upload = SimpleUploadedFile("x.txt", _PNG_BYTES, content_type="image/png")
    with pytest.raises(ValidationError, match="extension"):
        validate_upload(upload, allowed_mimetypes=["image/png"])


def test_validate_upload_restores_the_read_position_on_success() -> None:
    """The single most important test in this module: sniffing consumes the stream, and
    `validate_upload` must `file.seek(0)` in a `finally` — without it, whatever saves the file
    afterward would write a truncated-to-empty file.
    """
    upload = SimpleUploadedFile("x.png", _PNG_BYTES, content_type="image/png")
    validate_upload(upload, allowed_mimetypes=["image/png"])
    assert upload.read() == _PNG_BYTES


def test_validate_upload_restores_the_read_position_on_failure() -> None:
    """Same as above, but on the failure path — the `finally` matters just as much there."""
    upload = SimpleUploadedFile("x.png", _PNG_BYTES, content_type="image/png")
    with pytest.raises(ValidationError):
        validate_upload(upload, allowed_mimetypes=["image/jpeg"])
    assert upload.read() == _PNG_BYTES


def test_validate_upload_max_bytes_unset_uses_appkit_max_upload_bytes_setting(
    settings: object,
) -> None:
    settings.APPKIT = {**settings.APPKIT, "MAX_UPLOAD_BYTES": 10}  # type: ignore[attr-defined]
    upload = SimpleUploadedFile("x.png", _PNG_BYTES, content_type="image/png")
    with pytest.raises(ValidationError, match="too large"):
        validate_upload(upload, allowed_mimetypes=["image/png"])


def test_validate_upload_skips_the_extension_check_for_a_mimetype_with_no_table_entry() -> None:
    """`application/octet-stream` (the unrecognised-content fallback) has no
    `_EXTENSIONS_BY_MIMETYPE` entry — nothing to cross-check the extension against, so the
    function must not raise regardless of the filename.
    """
    upload = SimpleUploadedFile(
        "x.whatever", b"not a recognised signature", content_type="application/octet-stream"
    )
    validate_upload(upload, allowed_mimetypes=["application/octet-stream"])  # does not raise


# ---------------------------------------------------------------- validate_image


@requires_extra
def test_validate_image_returns_dimensions_and_format_for_a_png() -> None:
    upload = SimpleUploadedFile("x.png", _PNG_BYTES, content_type="image/png")
    info = validate_image(upload)
    assert info == ImageInfo(width=4, height=3, format="png")


@requires_extra
def test_validate_image_returns_dimensions_and_format_for_a_jpeg() -> None:
    upload = SimpleUploadedFile("x.jpg", _JPEG_BYTES, content_type="image/jpeg")
    info = validate_image(upload)
    assert info.width == 4
    assert info.height == 3
    assert info.format == "jpeg"


@requires_extra
def test_validate_image_rejects_dimensions_over_the_maximum() -> None:
    upload = SimpleUploadedFile("big.png", _BIG_PNG_BYTES, content_type="image/png")
    with pytest.raises(ValidationError, match="dimensions"):
        validate_image(upload, max_dimensions=(10, 10))


@requires_extra
def test_validate_image_within_max_dimensions_is_accepted() -> None:
    upload = SimpleUploadedFile("x.png", _PNG_BYTES, content_type="image/png")
    info = validate_image(upload, max_dimensions=(100, 100))
    assert info.width == 4


@requires_extra
def test_validate_image_restores_the_read_position_on_success() -> None:
    upload = SimpleUploadedFile("x.png", _PNG_BYTES, content_type="image/png")
    validate_image(upload)
    assert upload.read() == _PNG_BYTES


def test_validate_image_rejects_svg_by_default() -> None:
    upload = SimpleUploadedFile("x.svg", _SVG_BYTES, content_type="image/svg+xml")
    with pytest.raises(ValidationError, match="SVG"):
        validate_image(upload)


def test_validate_image_accepts_svg_when_allowed() -> None:
    upload = SimpleUploadedFile("x.svg", _SVG_BYTES, content_type="image/svg+xml")
    info = validate_image(upload, allow_svg=True)
    assert info == ImageInfo(width=10, height=20, format="svg")


def test_validate_image_svg_defaults_dimensions_to_zero_when_absent() -> None:
    upload = SimpleUploadedFile(
        "x.svg", b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', content_type="image/svg+xml"
    )
    info = validate_image(upload, allow_svg=True)
    assert info == ImageInfo(width=0, height=0, format="svg")


def test_validate_image_svg_ignores_a_malformed_numeric_dimension() -> None:
    """`width="12.34.56"` still matches the `[0-9.]+` capture group but `float()` rejects it —
    the malformed value is dropped (defaults to `0`) rather than raising.
    """
    upload = SimpleUploadedFile(
        "x.svg",
        b'<svg xmlns="http://www.w3.org/2000/svg" width="12.34.56" height="20"></svg>',
        content_type="image/svg+xml",
    )
    info = validate_image(upload, allow_svg=True)
    assert info == ImageInfo(width=0, height=20, format="svg")


def test_validate_image_svg_rejects_dimensions_over_the_maximum() -> None:
    upload = SimpleUploadedFile("x.svg", _SVG_BYTES, content_type="image/svg+xml")  # 10x20
    with pytest.raises(ValidationError, match="dimensions"):
        validate_image(upload, allow_svg=True, max_dimensions=(5, 5))


def test_validate_image_rejects_a_file_over_max_bytes() -> None:
    upload = SimpleUploadedFile("x.svg", _SVG_BYTES, content_type="image/svg+xml")
    with pytest.raises(ValidationError, match="too large"):
        validate_image(upload, max_bytes=10)


def test_validate_image_rejects_a_non_svg_non_image_mimetype() -> None:
    """A BMP header — a real, recognised-by-`puremagic` mimetype that isn't SVG and isn't in
    `_IMAGE_MIMETYPES`.
    """
    upload = SimpleUploadedFile("x.bmp", b"BM" + b"\x00" * 100, content_type="image/bmp")
    with pytest.raises(ValidationError, match="not a supported image type"):
        validate_image(upload)


@requires_extra
def test_validate_image_raises_validation_error_for_unreadable_image_data() -> None:
    """A valid PNG magic-byte signature (so `puremagic`/our own sniffing approves it) followed
    by garbage — `puremagic` sniffs the signature alone, but Pillow can't actually parse it,
    raising `PIL.UnidentifiedImageError`, which must be translated into our own
    `ValidationError` rather than propagating a third-party exception type.
    """
    corrupt_png = b"\x89PNG\r\n\x1a\n" + b"not a real chunk" * 4
    upload = SimpleUploadedFile("x.png", corrupt_png, content_type="image/png")
    with pytest.raises(ValidationError, match="Could not read image data"):
        validate_image(upload)


def test_validate_image_restores_the_read_position_on_the_svg_rejection_path() -> None:
    """Doesn't need the `images` extra — SVG rejection happens before Pillow is ever touched,
    so this exercises the `finally` on the bare-install leg too.
    """
    upload = SimpleUploadedFile("x.svg", _SVG_BYTES, content_type="image/svg+xml")
    with pytest.raises(ValidationError):
        validate_image(upload)
    assert upload.read() == _SVG_BYTES


def test_missing_images_extra_raises_actionable_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simulates Pillow being absent — covers the same `raise` branch the genuinely-bare-
    install leg exercises in `test_bare_install.py`, but (deliberately unmarked) runs in both
    legs.
    """
    monkeypatch.setitem(sys.modules, "PIL", None)
    upload = SimpleUploadedFile("x.png", _PNG_BYTES, content_type="image/png")
    with pytest.raises(ImportError, match=r"hjtdev-appkit\[images\]"):
        validate_image(upload)
