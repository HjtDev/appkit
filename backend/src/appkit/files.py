"""Upload validation via magic-byte sniffing, plus image validation.

Public surface (docs/CONTRACT.md §2.9), implemented in a later phase:

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
