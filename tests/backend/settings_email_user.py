"""Settings module proving `appkit.testing`'s `user`/`admin_user` fixtures build through
`get_user_model().USERNAME_FIELD` **reflectively**, against a non-`username`-keyed custom user
model (docs/CONTRACT.md §2.17's mandatory non-obvious-failure-path test).

Loaded only by the subprocess pytest leg in `test_testing_plugin.py`
(`test_reflective_user_fixture_against_a_non_username_user_model`) — never merged into
`tests/backend/settings.py`, which stays minimal per its own docstring. `AUTH_USER_MODEL` is
resolved once per process by Django, so this can't be exercised via `override_settings` in the
main run; it needs a genuinely separate process.
"""

from __future__ import annotations

from tests.backend.settings import *  # noqa: F403

INSTALLED_APPS = [*INSTALLED_APPS, "tests.backend.emailuser"]  # noqa: F405

AUTH_USER_MODEL = "emailuser.EmailUser"

DATABASES["default"]["NAME"] = "test_appkit_email_user"  # noqa: F405
