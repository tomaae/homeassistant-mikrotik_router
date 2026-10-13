"""Netwatch probes without a known state must not show as connected."""

from types import SimpleNamespace

import pytest

from custom_components.mikrotik_router.apiparser import parse_api
from custom_components.mikrotik_router.binary_sensor import MikrotikBinarySensor


def _netwatch(status):
    entry = {"host": "192.0.2.1", "disabled": False}
    if status is not None:
        entry["status"] = status
    return parse_api(
        data={},
        source=[entry],
        key="host",
        vals=[
            {"name": "host"},
            {"name": "status", "type": "bool", "default": None},
        ],
    )["192.0.2.1"]["status"]


def _is_on(value):
    sensor = object.__new__(MikrotikBinarySensor)
    sensor._data = {"status": value}
    sensor.entity_description = SimpleNamespace(data_attribute="status")
    return sensor.is_on


@pytest.mark.parametrize(
    ("status", "expected"),
    [("up", True), ("down", False), ("unknown", None), (None, None)],
)
def test_netwatch_status(status, expected) -> None:
    assert _netwatch(status) is expected
    assert _is_on(_netwatch(status)) is expected


def test_is_on_ignores_non_bool_values() -> None:
    assert _is_on("unknown") is None
