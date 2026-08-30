"""Upload validation via magic-byte sniffing, plus image validation.

Public surface (docs/CONTRACT.md §2.9):

    @dataclass(frozen=True)
    class ImageInfo:
        width: int
        height: int
        format: str

    def detect_mimetype(data: bytes) -> str: ...
        # puremagic stays internal — no third-party type leaks into this signature.

    def validate_upload(
        file: UploadedFile, *, allowed_mimetypes: Iterable[str], max_bytes: int = UNSET
    ) -> None: ...
        # raises django.core.exceptions.ValidationError; must file.seek(0) in a finally.
        # max_bytes accepts appkit.conf.UNSET, meaning "use APPKIT['MAX_UPLOAD_BYTES']".

    def validate_image(
        file: UploadedFile,
        *,
        max_bytes: int = UNSET,
        max_dimensions: tuple[int, int] | None = None,
        allow_svg: bool = False,
    ) -> ImageInfo: ...
        # Requires the `images` extra (Pillow) for anything beyond header-only dimension
        # reads. SVG is rejected unless allow_svg=True — an XML script-execution vector
        # otherwise.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import puremagic
from django.core.exceptions import ValidationError

from appkit.conf import UNSET, _Unset, get_setting

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.core.files.uploadedfile import UploadedFile

__all__ = ["ImageInfo", "detect_mimetype", "validate_image", "validate_upload"]

_INSTALL_HINT_IMAGES = (
    'Install with: uv add "hjtdev-appkit[images]" (or: pip install "hjtdev-appkit[images]")'
)

# Explicit, hardcoded extension<->mimetype agreement table — never mimetypes.guess_extension,
# whose answer depends on the host OS's /etc/mime.types and disagrees across systems for
# exactly the formats this module exists to check (docs/CONTRACT.md §2.9).
_EXTENSIONS_BY_MIMETYPE: dict[str, frozenset[str]] = {
    "image/jpeg": frozenset({".jpg", ".jpeg"}),
    "image/png": frozenset({".png"}),
    "image/gif": frozenset({".gif"}),
    "image/webp": frozenset({".webp"}),
    "image/svg+xml": frozenset({".svg"}),
    "application/pdf": frozenset({".pdf"}),
    "text/plain": frozenset({".txt"}),
    "application/zip": frozenset({".zip"}),
    "application/json": frozenset({".json"}),
    "video/mp4": frozenset({".mp4"}),
    "audio/mpeg": frozenset({".mp3"}),
}

_IMAGE_MIMETYPES: frozenset[str] = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})
_SVG_MIMETYPE = "image/svg+xml"

# SVG is plain XML — puremagic's magic-byte database won't identify it, so it needs an explicit
# check ahead of the byte-sniffing path.
_SVG_PROLOG_RE = re.compile(rb"<\?xml\b")
_SVG_TAG_RE = re.compile(rb"<svg\b")
_SVG_DIMENSION_RE = re.compile(rb'(width|height)\s*=\s*["\']?\s*([0-9.]+)')


@dataclass(frozen=True)
class ImageInfo:
    """Header-derived image metadata returned by `validate_image`."""

    width: int
    height: int
    format: str


def _looks_like_svg(data: bytes) -> bool:
    head = data[:2048].lstrip()
    if _SVG_PROLOG_RE.match(head):
        return bool(_SVG_TAG_RE.search(data[:4096]))
    return bool(_SVG_TAG_RE.match(head))


def detect_mimetype(data: bytes) -> str:
    """Magic-byte sniffing via `puremagic` — never the client-supplied `Content-Type` header
    and never the filename extension, both attacker-controlled and routinely wrong.

    Returns `"application/octet-stream"` for anything unrecognised rather than raising, so a
    caller decides what "unknown" means for its own upload policy.
    """
    if _looks_like_svg(data):
        return _SVG_MIMETYPE
    try:
        mimetype = puremagic.from_string(data, mime=True)
    except puremagic.PureError:
        return "application/octet-stream"
    return mimetype or "application/octet-stream"


def _extension_of(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def _check_extension_agreement(filename: str, mimetype: str) -> None:
    valid_extensions = _EXTENSIONS_BY_MIMETYPE.get(mimetype)
    if valid_extensions is None:
        return  # no table entry for this mimetype — nothing to cross-check against
    if _extension_of(filename) not in valid_extensions:
        raise ValidationError(
            f"File extension of {filename!r} does not match its detected type {mimetype!r}.",
            code="appkit_extension_mismatch",
        )


def validate_upload(
    file: UploadedFile[bytes],
    *,
    allowed_mimetypes: Iterable[str],
    max_bytes: int | _Unset = UNSET,
) -> None:
    """Sniffs `file`, checking size, detected mimetype, and extension/mimetype agreement.

    `max_bytes=UNSET` resolves to `APPKIT["MAX_UPLOAD_BYTES"]` — a semantic/business-rule
    limit ("reject a 50 MB avatar"), not a DoS control; Django's own
    `DATA_UPLOAD_MAX_MEMORY_SIZE`/`FILE_UPLOAD_MAX_MEMORY_SIZE` are the actual memory/disk
    boundary, already enforced before this function ever runs.

    Raises `django.core.exceptions.ValidationError` naming which check failed.

    **The single most important line in this module:** sniffing consumes the file's read
    position, so `file.seek(0)` runs in a `finally` regardless of outcome — without it,
    whatever saves the file afterward (a serializer's `.save()`) would write a
    truncated-to-empty file.
    """
    limit = get_setting("MAX_UPLOAD_BYTES") if isinstance(max_bytes, _Unset) else max_bytes
    allowed = frozenset(allowed_mimetypes)
    try:
        file.seek(0)
        size = getattr(file, "size", None)
        if size is not None and size > limit:
            raise ValidationError(
                f"File is too large: {size} bytes exceeds the {limit} byte limit.",
                code="appkit_file_too_large",
            )

        head = file.read(4096)
        mimetype = detect_mimetype(head)
        if mimetype not in allowed:
            raise ValidationError(
                f"File type {mimetype!r} is not an allowed upload type.",
                code="appkit_mimetype_not_allowed",
            )

        _check_extension_agreement(getattr(file, "name", "") or "", mimetype)
    finally:
        file.seek(0)


def _pil_image_module() -> Any:
    """Lazily imports `PIL.Image`, behind the `images` extra.

    A missing extra must fail with an actionable message, never a bare `ImportError` — this
    path is unit-tested by simulating the import failure.
    """
    try:
        from PIL import Image
    except ImportError as exc:
        raise ImportError(
            "appkit.files.validate_image requires the 'Pillow' package for image dimension "
            f"reading. {_INSTALL_HINT_IMAGES}"
        ) from exc
    return Image


def _svg_image_info(
    file: UploadedFile[bytes], *, max_dimensions: tuple[int, int] | None
) -> ImageInfo:
    """Reads `width`/`height` attributes off the SVG root element via a bounded regex scan —
    never touches Pillow, which doesn't support SVG at all.

    Neither attribute is guaranteed to be present on a valid SVG (viewBox-only documents are
    legal); both default to `0` when absent or non-numeric, and `max_dimensions` is skipped
    when either dimension is unknown rather than comparing against a meaningless `0`.
    """
    file.seek(0)
    head = file.read(4096)
    dimensions: dict[str, int] = {}
    for match in _SVG_DIMENSION_RE.finditer(head):
        key = match.group(1).decode()
        try:
            dimensions[key] = int(float(match.group(2)))
        except ValueError:
            continue

    width = dimensions.get("width", 0)
    height = dimensions.get("height", 0)
    if max_dimensions is not None and width and height:
        max_width, max_height = max_dimensions
        if width > max_width or height > max_height:
            raise ValidationError(
                f"Image dimensions {width}x{height} exceed the maximum {max_width}x{max_height}.",
                code="appkit_dimensions_too_large",
            )
    return ImageInfo(width=width, height=height, format="svg")


def validate_image(
    file: UploadedFile[bytes],
    *,
    max_bytes: int | _Unset = UNSET,
    max_dimensions: tuple[int, int] | None = None,
    allow_svg: bool = False,
) -> ImageInfo:
    """Everything `validate_upload` does, restricted to image mimetypes, plus a
    decompression-bomb-aware dimension check.

    **SVG is rejected unless `allow_svg=True`** — SVG is XML, and XML is a script-execution
    vector (embedded `<script>`, external entity references) that magic-byte sniffing alone
    happily approves as "a valid file of the claimed type." When allowed, SVG dimensions are
    read without ever touching Pillow (see `_svg_image_info`).

    For raster formats, **Pillow is the header reader**: `PIL.Image.open()` is lazy and yields
    `.size`/`.format` from the header without decoding pixel data — this *is* the
    decompression-bomb-safe read, and it requires the `images` extra. Missing the extra raises
    the same actionable `ImportError` pattern as `appkit.crypto`.

    `seek(0)` runs in a `finally`, same as `validate_upload`, for the same corruption reason.

    Raises `django.core.exceptions.ValidationError` naming which check failed; `ImportError` if
    the `images` extra is needed and absent.
    """
    limit = get_setting("MAX_UPLOAD_BYTES") if isinstance(max_bytes, _Unset) else max_bytes
    allowed = set(_IMAGE_MIMETYPES)
    if allow_svg:
        allowed.add(_SVG_MIMETYPE)

    try:
        file.seek(0)
        size = getattr(file, "size", None)
        if size is not None and size > limit:
            raise ValidationError(
                f"File is too large: {size} bytes exceeds the {limit} byte limit.",
                code="appkit_file_too_large",
            )

        head = file.read(4096)
        mimetype = detect_mimetype(head)

        if mimetype == _SVG_MIMETYPE:
            if not allow_svg:
                raise ValidationError(
                    "SVG uploads are rejected by default (XML is a script-execution vector). "
                    "Pass allow_svg=True to accept them.",
                    code="appkit_svg_not_allowed",
                )
            return _svg_image_info(file, max_dimensions=max_dimensions)

        if mimetype not in allowed:
            raise ValidationError(
                f"File type {mimetype!r} is not a supported image type.",
                code="appkit_mimetype_not_allowed",
            )

        _check_extension_agreement(getattr(file, "name", "") or "", mimetype)

        image_module = _pil_image_module()
        file.seek(0)
        try:
            with image_module.open(file) as img:
                width, height = img.size
                image_format = (img.format or "").lower()
        except image_module.UnidentifiedImageError as exc:
            raise ValidationError(
                f"Could not read image data: {exc}", code="appkit_unreadable_image"
            ) from exc

        if max_dimensions is not None:
            max_width, max_height = max_dimensions
            if width > max_width or height > max_height:
                raise ValidationError(
                    f"Image dimensions {width}x{height} exceed the maximum "
                    f"{max_width}x{max_height}.",
                    code="appkit_dimensions_too_large",
                )

        return ImageInfo(width=width, height=height, format=image_format)
    finally:
        file.seek(0)
