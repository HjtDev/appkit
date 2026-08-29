"""Scratch throttle classes for `appkit.checks.check_num_proxies_throttle_agreement`
(`appkit.W006`) tests only.

Referenced exclusively by dotted-string path inside `override_settings(REST_FRAMEWORK={
"DEFAULT_THROTTLE_CLASSES": [...]})` in test_checks.py — never imported there directly.
`rest_framework.throttling.SimpleRateThrottle`'s class body reads
`api_settings.DEFAULT_THROTTLE_RATES` at class-DEFINITION time (`THROTTLE_RATES =
api_settings.DEFAULT_THROTTLE_RATES`), which raises `ImproperlyConfigured` if evaluated before
Django settings exist — exactly the `appkit.testing` deferred-import hazard (see that module's
own docstring) reproduced on the test side: a module-scope `from rest_framework.throttling
import SimpleRateThrottle` in test_checks.py crashes pytest's collection phase, before
pytest-django has configured settings. Keeping these classes in their own module that's only
resolved later, via `import_string` inside the check under test, sidesteps the landmine
entirely — the same reason `urls_w006.py`/`urls_throttling.py` are separate modules too.
"""

from __future__ import annotations

from rest_framework.throttling import BaseThrottle, SimpleRateThrottle


class CustomSimpleRateThrottle(SimpleRateThrottle):
    """A host's own SimpleRateThrottle subclass, inheriting get_ident unchanged — must be
    caught by class resolution, not a name match against DRF's own built-in classes.
    """

    scope = "custom"


class CustomThrottleWithOwnGetIdent(SimpleRateThrottle):
    """Overrides get_ident itself — DRF's whole-header-join hazard isn't in play, so this must
    never trigger appkit.W006 no matter how it's configured.
    """

    scope = "custom-safe"

    def get_ident(self, request: object) -> str:
        return "fixed"


class NotAThrottleAtAll(BaseThrottle):
    """A BaseThrottle subclass that is NOT a SimpleRateThrottle — get_ident() isn't the
    whole-header-join implementation at all, so this must never trigger appkit.W006.
    """

    def get_ident(self, request: object) -> str:
        return "n/a"
