"""The RouterOS API sockets are closed instead of being left to the GC."""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mikrotik_router.const import DOMAIN
from custom_components.mikrotik_router import config_flow
from custom_components.mikrotik_router.mikrotikapi import MikrotikAPI


def _api() -> MikrotikAPI:
    return MikrotikAPI("192.0.2.1", "user", "pw", use_ssl=False)


def test_close_closes_socket_and_refuses_reconnect() -> None:
    api = _api()
    connection = MagicMock()
    api._connection = connection
    api._connected = True

    api.close()

    connection.close.assert_called_once()
    assert not api.connected()
    with patch("librouteros.connect") as connect:
        assert not api.connect()
        assert not api.connection_check()
        connect.assert_not_called()


def test_disconnect_closes_socket() -> None:
    api = _api()
    connection = MagicMock()
    api._connection = connection
    api._connected = True

    api.disconnect("test", "boom")

    connection.close.assert_called_once()
    assert api._connection is None


def test_close_ignores_socket_errors() -> None:
    api = _api()
    api._connection = MagicMock()
    api._connection.close.side_effect = OSError("gone")

    api.close()

    assert api._connection is None


def test_reconnect_closes_previous_socket() -> None:
    api = _api()
    old = MagicMock()
    api._connection = old
    with patch("librouteros.connect", return_value=MagicMock()):
        assert api.connect()

    old.close.assert_called_once()


def test_validate_input_closes_api() -> None:
    api = MagicMock()
    api.connect.return_value = False
    api.error = "cannot_connect"
    user_input = {
        "host": "192.0.2.1",
        "username": "u",
        "password": "p",
        "port": 0,
        "ssl": False,
        "verify_ssl": False,
    }
    with patch.object(config_flow, "MikrotikAPI", return_value=api):
        assert config_flow.validate_input(user_input) == (None, "cannot_connect")

    api.close.assert_called_once()


async def _fake_update(self):
    self.ds["access"] = ["write", "policy", "reboot", "test"]
    self.ds["routerboard"] = {
        "routerboard": True,
        "serial-number": "HEX123",
        "model": "RB5009",
        "current-firmware": "7.20",
        "upgrade-firmware": "7.20",
    }
    self.ds["resource"] = {
        "board-name": "RB5009",
        "platform": "MikroTik",
        "version": "7.20.1",
    }
    return self.ds


async def _fake_tracker_update(self):
    return None


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    yield


async def test_unload_closes_both_apis(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        minor_version=3,
        unique_id="routerboard:hex123",
        data={
            CONF_NAME: "Mikrotik",
            CONF_HOST: "192.0.2.1",
            CONF_PORT: 0,
            CONF_SSL: False,
            CONF_VERIFY_SSL: False,
            CONF_USERNAME: "u",
            CONF_PASSWORD: "p",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.mikrotik_router.coordinator.MikrotikCoordinator._async_update_data",
            _fake_update,
        ),
        patch(
            "custom_components.mikrotik_router.coordinator.MikrotikTrackerCoordinator._async_update_data",
            _fake_tracker_update,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    runtime = entry.runtime_data
    assert not runtime.data_coordinator.api._closed
    assert not runtime.tracker_coordinator.api._closed

    assert await hass.config_entries.async_unload(entry.entry_id)

    assert runtime.data_coordinator.api._closed
    assert runtime.tracker_coordinator.api._closed
