"""appkit's ``AppConfig``.

``INSTALLED_APPS`` membership is confirmed, not merely left standing (docs/CONTRACT.md §5), for
two reasons: translations become real only when appkit is a genuine ``INSTALLED_APPS`` member
(``standard_exception_handler``'s user-facing strings are wrapped in ``gettext_lazy`` and
discovered via a shipped ``locale/`` directory), and the system checks in :mod:`appkit.checks`
must be registered from ``ready()`` to run at all.

appkit defines no models, so there is no ``default_auto_field`` to set.
"""

from __future__ import annotations

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AppKitConfig(AppConfig):
    name = "appkit"
    verbose_name = _("App Kit")

    def ready(self) -> None:
        from django.core.checks import register

        from appkit import checks

        register(checks.check_request_id_middleware)
        register(checks.check_exception_handler)
        register(checks.check_middleware_order)
        register(checks.check_unknown_settings_keys)
        register(checks.check_throttle_scopes)
        register(checks.check_logging_filter)
