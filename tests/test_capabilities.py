"""Regression tests for RouterOS wireless capability detection."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from custom_components.mikrotik_router.coordinator import MikrotikCoordinator


@pytest.mark.parametrize(
    ("architecture", "version", "packages", "expected", "capsman"),
    [
        ("smips", (7, 24), ["routeros", "wireless"], ["wireless"], True),
        ("SMIPS", (7, 24), ["routeros", "wireless"], ["wireless"], True),
        ("smips", (7, 24), ["routeros"], [], False),
        ("smips", (7, 12), ["routeros"], ["wireless"], True),
        ("smips", (6, 49), ["routeros", "wireless"], ["wireless"], True),
        ("mipsbe", (7, 24), ["routeros", "wireless"], ["wifi", "wireless"], True),
        ("arm", (7, 24), ["routeros", "wifi-qcom-ac"], ["wifi"], False),
        ("arm64", (7, 24), ["routeros", "wifi-qcom"], ["wifi"], False),
        ("arm64", (7, 12), ["routeros", "wifiwave2"], ["wifiwave2", "wireless"], True),
        ("x86_64", (7, 24), ["routeros"], ["wifi"], False),
    ],
)
def test_wireless_capabilities(architecture, version, packages, expected, capsman):
    """SMIPS skips Wi-Fi while legacy wireless and other architectures still work."""
    api = Mock()
    api.query.return_value = [{"name": name, "disabled": False} for name in packages]
    coordinator = SimpleNamespace(
        api=api,
        ds={"resource": {"architecture-name": architecture}},
        major_fw_version=version[0],
        minor_fw_version=version[1],
        host="router.example",
    )

    MikrotikCoordinator.get_capabilities(coordinator)

    assert coordinator._wifimodules == expected
    assert coordinator.support_wireless is bool(expected)
    assert coordinator.support_capsman is capsman
    api.query.assert_called_once_with("/system/package")
