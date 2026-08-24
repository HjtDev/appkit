"""Query-param validation, HTML sanitisation, and an ORM lookup allowlist for user-driven
filtering.

No custom validation framework — DRF serializers already do the work; this module adds a thin
helper for validating ``request.query_params`` through a serializer, not a new declaration
syntax. No generic XSS/SQL-injection scanner either: the ORM already prevents SQL injection, and
string-scanning for ``<script>`` is a blocklist that provides false confidence, not real
protection (docs/CONTRACT.md §J).

Public surface (docs/CONTRACT.md §2.8), implemented in a later phase:

    def validate_query_params(serializer_class: type[S], params: QueryDict) -> S: ...
        # raises rest_framework.exceptions.ValidationError

    def sanitize_html(value: str, *, allowed_tags: Iterable[str] | None = None) -> str: ...
        # default tag set: p, br, strong, em, a, ul, ol, li

    def strip_html(value: str) -> str: ...

    ALLOWED_LOOKUPS: Final[frozenset[str]]
        # eq/exact, iexact, contains, icontains, startswith, endswith, gt, gte, lt, lte, in,
        # isnull, range. regex and iregex are excluded on purpose.

    def validate_lookup(lookup: str) -> bool: ...

    def safe_filter_kwargs(
        params: QueryDict, allowed_fields: Iterable[str], *, allow_relations: bool = False
    ) -> dict[str, Any]: ...
        # allow_relations exists specifically to prevent filter-based data exfiltration across
        # relations when left at its default False.
"""

from __future__ import annotations
