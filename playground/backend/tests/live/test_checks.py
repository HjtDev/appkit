"""The system checks, both directions (docs/APP-DESIGN.md §11.2's Phase 6 brief): a correctly-
wired playground must produce silence, and each of the seven check IDs must fire exactly when
its corresponding wiring is broken — proven against the real running container, not a
locally-simulated settings module.
"""

from __future__ import annotations

import pytest

from tests.live.conftest import run_manage

BROKEN_CASES = [
    ("config.broken.no_middleware", "appkit.E001"),
    ("config.broken.drf_default_handler", "appkit.E002"),
    ("config.broken.foreign_handler", "appkit.W001"),
    ("config.broken.middleware_order", "appkit.W002"),
    ("config.broken.unknown_appkit_key", "appkit.W003"),
    ("config.broken.no_throttle_rate", "appkit.W004"),
    ("config.broken.no_logging_filter", "appkit.W005"),
]


def test_correctly_wired_playground_is_silent() -> None:
    """The positive case matters more than any negative one: a check that fires against a
    correctly-configured real host is one someone will silence.
    """
    result = run_manage(["check"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "System check identified no issues" in result.stdout + result.stderr
    assert "appkit." not in result.stdout


@pytest.mark.parametrize(("settings_module", "expected_id"), BROKEN_CASES)
def test_broken_wiring_fires_exactly_its_own_id(settings_module: str, expected_id: str) -> None:
    result = run_manage(["check"], settings=settings_module)
    output = result.stdout + result.stderr
    assert expected_id in output, output

    other_ids = {cid for _, cid in BROKEN_CASES} - {expected_id}
    fired_others = {cid for cid in other_ids if cid in output}
    assert not fired_others, f"{settings_module} unexpectedly also fired {fired_others}: {output}"
