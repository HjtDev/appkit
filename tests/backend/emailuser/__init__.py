"""Test-only Django app providing a non-`username` `USERNAME_FIELD` custom user model.

Exists solely to prove `appkit.testing`'s `user`/`admin_user` fixtures build through
`get_user_model().USERNAME_FIELD` reflectively (docs/CONTRACT.md §2.17) — never listed in the
main `tests/backend/settings.py`, only in `tests/backend/settings_email_user.py`, loaded by a
dedicated subprocess pytest leg in `test_testing_plugin.py`.
"""
