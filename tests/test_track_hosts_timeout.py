"""The host presence timeout is bounded."""

from datetime import timedelta

import pytest

from custom_components.mikrotik_router.const import (
    CONF_TRACK_HOSTS_TIMEOUT,
    DEFAULT_TRACK_HOST_TIMEOUT,
    MAX_TRACK_HOST_TIMEOUT,
)
from custom_components.mikrotik_router.helper import track_hosts_timeout


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (180, 180),
        (180.0, 180),
        (0, 1),
        (-5, 1),
        (10**12, MAX_TRACK_HOST_TIMEOUT),
        ("60", 60),
        ("soon", DEFAULT_TRACK_HOST_TIMEOUT),
        (None, DEFAULT_TRACK_HOST_TIMEOUT),
    ],
)
def test_timeout_is_clamped(value, expected) -> None:
    """Zero, negative and huge stored values can't break presence tracking."""
    result = track_hosts_timeout({CONF_TRACK_HOSTS_TIMEOUT: value})
    assert result == timedelta(seconds=expected)


def test_default() -> None:
    assert track_hosts_timeout({}) == timedelta(seconds=DEFAULT_TRACK_HOST_TIMEOUT)
