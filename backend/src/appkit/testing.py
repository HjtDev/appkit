"""The opt-in pytest plugin — fixtures and an envelope assertion helper.

Opt-in is explicit: ``-p appkit.testing`` in the consumer's own ``addopts``
(``tool.pytest.ini_options``), never automatic. This module deliberately registers NO
``pytest11`` entry point in pyproject.toml — two alternatives were considered and both rejected
(docs/CONTRACT.md §2.17):

  * A ``pytest11`` entry point would auto-load these fixtures into EVERY host's test suite the
    moment appkit is merely installed (which is always, transitively) — invisible magic adding
    fixtures nobody asked for into a namespace they didn't opt into.
  * ``pytest_plugins = ["appkit.testing"]`` only works from the rootdir conftest in pytest 7+;
    an app package's own ``testpaths = ["../tests/backend"]`` means the package's own conftest
    isn't the rootdir conftest, so this wouldn't even work by default for the app packages that
    need it most.

A consuming app wires this up itself, in its own ``pyproject.toml``::

    [tool.pytest.ini_options]
    addopts = "-p appkit.testing ..."

Public surface (docs/CONTRACT.md §2.17), implemented in a later phase:

    @pytest.fixture
    def api_client() -> APIClient: ...
        # An unauthenticated DRF APIClient.

    @pytest.fixture
    def user(db) -> AbstractBaseUser: ...
        # Built through get_user_model().USERNAME_FIELD REFLECTIVELY, not a hardcoded
        # create_user(username=...) call — must work against a host on an email-based custom
        # user model.

    @pytest.fixture
    def admin_user(db) -> AbstractBaseUser: ...
        # Same reflective construction, staff/admin.

    @pytest.fixture
    def auth_client(api_client, user) -> APIClient: ...

    @pytest.fixture
    def admin_client(api_client, admin_user) -> APIClient: ...

    @pytest.fixture
    def frozen_request_id() -> Iterator[str]: ...
        # Yields a fixed request-ID string; asserts it's restored to "-" (or the prior value)
        # on fixture teardown, making RequestIDMiddleware's reset-in-finally contract directly
        # assertable from a consuming app's own tests.

    @pytest.fixture
    def clear_cache() -> None: ...
        # Deliberately NOT autouse — under `pytest -n auto` (pytest-xdist) against a shared
        # Redis instance, an autouse fixture clearing the cache between every test would clear
        # another xdist worker's in-flight test data too.

    def assert_error_envelope(response: Response, *, code: str, status: int) -> None: ...
        # Plain function, not a fixture. Shared assertion for the docs/CONTRACT.md §1 envelope
        # so nine installed apps don't hand-roll nine slightly different assertions. Raises the
        # test framework's own AssertionError with a diff-friendly message on mismatch.
"""

from __future__ import annotations
