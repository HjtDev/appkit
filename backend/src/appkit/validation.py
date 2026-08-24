"""Query-param validation, HTML sanitisation, and an ORM lookup allowlist for user-driven
filtering.

No custom validation framework — DRF serializers already do the work; this module adds a thin
helper for validating ``request.query_params`` through a serializer, not a new declaration
syntax. No generic XSS/SQL-injection scanner either: the ORM already prevents SQL injection, and
string-scanning for ``<script>`` is a blocklist that provides false confidence, not real
protection (docs/CONTRACT.md §J).

Public surface (docs/CONTRACT.md §2.8):

    def validate_query_params(serializer_class: type[S], params: QueryDict) -> S: ...
        # raises rest_framework.exceptions.ValidationError

    def sanitize_html(value: str, *, allowed_tags: Iterable[str] | None = None) -> str: ...
        # default tag set: p, br, strong, em, a, ul, ol, li

    def strip_html(value: str) -> str: ...

    ALLOWED_LOOKUPS: Final[frozenset[str]]
        # exact, iexact, contains, icontains, startswith, endswith, gt, gte, lt, lte, in,
        # isnull, range. regex and iregex are excluded on purpose.
        #
        # Reading flag: docs/CONTRACT.md §2.8 writes the first member as "eq/exact" — only
        # "exact" is a real Django ORM lookup (there is no "eq"), so only "exact" goes in the
        # set. Admitting a literal "eq" would let a caller build filter(x__eq=...) and get a
        # FieldError from a function whose entire job is to prevent exactly that.

    def validate_lookup(lookup: str) -> bool: ...

    def safe_filter_kwargs(
        params: QueryDict, allowed_fields: Iterable[str], *, allow_relations: bool = False
    ) -> dict[str, Any]: ...
        # allow_relations exists specifically to prevent filter-based data exfiltration across
        # relations when left at its default False.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import nh3

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.http import QueryDict
    from rest_framework.serializers import Serializer

__all__ = [
    "ALLOWED_LOOKUPS",
    "safe_filter_kwargs",
    "sanitize_html",
    "strip_html",
    "validate_lookup",
    "validate_query_params",
]

#: nh3's own default HTML tag allowlist is much larger than this — this is appkit's
#: deliberately minimal default for "safe rich text" (a comment body, a bio field), not nh3's.
_DEFAULT_ALLOWED_TAGS: Final[frozenset[str]] = frozenset(
    {"p", "br", "strong", "em", "a", "ul", "ol", "li"}
)

#: The ORM lookup allowlist. `regex`/`iregex` are excluded on purpose — a user-controlled regex
#: against Postgres is a ReDoS vector, and this allowlist's whole job is to be the thing an app
#: checks before building a `filter(**kwargs)` from user input.
ALLOWED_LOOKUPS: Final[frozenset[str]] = frozenset(
    {
        "exact",
        "iexact",
        "contains",
        "icontains",
        "startswith",
        "endswith",
        "gt",
        "gte",
        "lt",
        "lte",
        "in",
        "isnull",
        "range",
    }
)


def validate_query_params[S: Serializer[Any]](serializer_class: type[S], params: QueryDict) -> S:
    """Runs `params` through `serializer_class` for read-side validation, returning the
    validated serializer instance.

    Raises `rest_framework.exceptions.ValidationError` on invalid input — deliberately DRF's
    own exception, so it flows straight into `standard_exception_handler` without a
    translation layer. This is a thin helper pointing DRF serializers at
    `request.query_params` instead of `request.data`, not a parallel validation framework.
    """
    serializer = serializer_class(data=params)
    serializer.is_valid(raise_exception=True)
    return serializer


def sanitize_html(value: str, *, allowed_tags: Iterable[str] | None = None) -> str:
    """`nh3`-based allowlist HTML sanitisation. `allowed_tags=None` uses the documented minimal
    default tag set (`p`, `br`, `strong`, `em`, `a`, `ul`, `ol`, `li`).

    Never raises; malformed HTML is repaired, not rejected, matching `nh3`'s own behaviour.
    `<script>` tags and `on*=` event-handler attributes are stripped even when nested inside an
    otherwise-allowed tag (`<a onmouseover="...">`) — `nh3` strips any tag not in `tags` (down
    to its inert text content, never its markup) and any attribute not in its own default
    attribute allowlist (which never includes an event handler), at every nesting depth, not
    only the top level.
    """
    tags = frozenset(allowed_tags) if allowed_tags is not None else _DEFAULT_ALLOWED_TAGS
    return nh3.clean(value, tags=set(tags))


def strip_html(value: str) -> str:
    """Removes all tags, returning plain text. For fields that must never contain markup at
    all (a display name), not fields that may contain safe rich text.
    """
    return nh3.clean(value, tags=set())


def validate_lookup(lookup: str) -> bool:
    """Pure membership check against `ALLOWED_LOOKUPS`. Never raises."""
    return lookup in ALLOWED_LOOKUPS


def _split_filter_key(key: str, *, allow_relations: bool) -> tuple[str, str] | None:
    """Parses `key` into `(field_path, lookup)`, or `None` if the shape isn't allowed.

    Counts `__`-delimited segments rather than checking a prefix: `allowed_fields=["created_at"]`
    must accept `?created_at__gte=x` (2 segments, second is a valid lookup) and reject
    `?created_at__related__gte=x` (3 segments) even though the first segment matches.
    """
    segments = key.split("__")

    if not allow_relations:
        if len(segments) == 1:
            return segments[0], "exact"
        if len(segments) == 2 and segments[1] in ALLOWED_LOOKUPS:
            return segments[0], segments[1]
        return None

    # allow_relations=True: any number of `field__field__...` segments is a candidate relation
    # path; only the *trailing* segment is ever treated as a lookup, and only if it's a
    # recognised one — the caller's `allowed_fields` is what actually decides which paths exist.
    if len(segments) >= 2 and segments[-1] in ALLOWED_LOOKUPS:
        return "__".join(segments[:-1]), segments[-1]
    return "__".join(segments), "exact"


def _coerce_filter_value(lookup: str, raw: str) -> Any:
    """Type-coerces a raw query-param string for the given lookup.

    Without the `isnull` coercion, `?x__isnull=false` would filter as `True` (any non-empty
    string is truthy) — a silent wrong-results bug, not a style choice.
    """
    if lookup in ("in", "range"):
        return [item.strip() for item in raw.split(",") if item.strip()]
    if lookup == "isnull":
        return raw.strip().lower() in ("1", "true", "yes")
    return raw


def safe_filter_kwargs(
    params: QueryDict, allowed_fields: Iterable[str], *, allow_relations: bool = False
) -> dict[str, Any]:
    """Builds a `.filter()`-safe kwargs dict from raw query params.

    Only `allowed_fields` may appear, only `ALLOWED_LOOKUPS` suffixes are accepted, and unknown
    params are **dropped, not errored** — a client typo degrades to "no filter applied", not a
    500.

    `allow_relations=False` (the default) is the load-bearing default and the whole point of
    this function's existence: with it, `field__related__field` double-underscore traversal is
    rejected outright — `?user__email__icontains=` cannot be used to exfiltrate another table's
    data through a filter an app author only meant to expose one field of. Passing
    `allow_relations=True` opts a specific relation path in only when that exact dotted path
    (e.g. `"user__email"`) is itself listed in `allowed_fields`.
    """
    allowed = frozenset(allowed_fields)
    result: dict[str, Any] = {}
    for key in params:
        parsed = _split_filter_key(key, allow_relations=allow_relations)
        if parsed is None:
            continue
        field_path, lookup = parsed
        if field_path not in allowed:
            continue
        raw = params.get(key)
        if raw is None:
            continue
        kwarg_key = field_path if lookup == "exact" else f"{field_path}__{lookup}"
        result[kwarg_key] = _coerce_filter_value(lookup, raw)
    return result
