"""Kid Control client traffic rates use a baseline per device."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from custom_components.mikrotik_router import coordinator as coordinator_module
from custom_components.mikrotik_router.coordinator import (
    MikrotikCoordinator,
    _counter_delta,
)

MAC1 = "AA:BB:CC:DD:EE:01"
MAC2 = "AA:BB:CC:DD:EE:02"


def _device(mac, up, down):
    return {"mac-address": mac, "bytes-up": up, "bytes-down": down}


@pytest.fixture
def poll():
    coordinator = object.__new__(MikrotikCoordinator)
    coordinator.notified_flags = []
    coordinator.ds = {
        "host": {
            mac: {"address": "192.0.2.1", "mac-address": mac, "host-name": mac}
            for mac in (MAC1, MAC2)
        },
        "client_traffic": {},
    }
    coordinator.api = MagicMock()

    def run(now, devices):
        coordinator.api.query.return_value = devices
        with patch.object(coordinator_module, "monotonic", return_value=now):
            coordinator.process_kid_control_devices()
        return coordinator.ds["client_traffic"]

    run.api = coordinator.api
    return run


def test_counter_delta() -> None:
    assert _counter_delta(150, 100) == 50
    assert _counter_delta(20, 100) == 20  # reset
    assert _counter_delta(100, None) is None
    assert _counter_delta("", 100) is None


def test_first_sample_is_unknown_then_rate(poll) -> None:
    traffic = poll(100, [_device(MAC1, 5000, 9000)])
    assert traffic[MAC1]["tx"] is None
    assert traffic[MAC1]["rx"] is None

    traffic = poll(160, [_device(MAC1, 6200, 9600)])
    assert traffic[MAC1]["tx"] == 20
    assert traffic[MAC1]["rx"] == 10


def test_missed_sample_keeps_the_rate_correct(poll) -> None:
    """1000 B at t=0, absent at t=60, 13000 B at t=120 is 100 B/s, not 200."""
    poll(0, [_device(MAC1, 1000, 0)])
    poll(60, [])
    traffic = poll(120, [_device(MAC1, 13000, 0)])
    assert traffic[MAC1]["tx"] == 100


def test_new_device_does_not_publish_its_lifetime_counter(poll) -> None:
    poll(0, [_device(MAC1, 0, 0)])
    traffic = poll(60, [_device(MAC1, 600, 0), _device(MAC2, 9_000_000, 0)])
    assert traffic[MAC2]["tx"] is None  # first sample: unknown, no spike
    traffic = poll(120, [_device(MAC1, 1200, 0), _device(MAC2, 9_000_600, 0)])

    assert traffic[MAC1]["tx"] == 10
    assert traffic[MAC2]["tx"] == 10


def test_counter_reset_does_not_spike(poll) -> None:
    poll(0, [_device(MAC1, 1_000_000, 0)])
    traffic = poll(60, [_device(MAC1, 600, 0)])
    assert traffic[MAC1]["tx"] == 10


def test_quick_second_read_is_ignored(poll, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    poll(0, [_device(MAC1, 0, 0)])
    poll(60, [_device(MAC1, 600, 0)])
    traffic = poll(60.2, [_device(MAC1, 650, 0)])
    assert traffic[MAC1]["tx"] == 10

    # The quick read must not move the baseline: the next normal sample is
    # still measured from t=60 / 600 B (600 B over 60 s = 10 B/s).
    traffic = poll(120, [_device(MAC1, 1200, 0)])
    assert traffic[MAC1]["tx"] == 10


def test_kid_control_resets_the_shared_accounting_baseline(poll) -> None:
    """After RouterOS 7 polls, a switch back to accounting starts fresh."""
    poll.api.client_traffic_last_run = 123.0
    poll(10, [_device(MAC1, 0, 0)])
    assert poll.api.client_traffic_last_run is None
