from datetime import timedelta
from unittest.mock import patch

import librouteros
import pytest

from homeassistant import data_entry_flow
from custom_components import mikrotik_router

from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SSL,
)

from . import MOCK_DATA

from tests.common import MockConfigEntry

DEMO_USER_INPUT = {
    CONF_NAME: "Home router",
    CONF_HOST: "0.0.0.0",
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_PORT: 8278,
    CONF_SSL: True,
}

DEMO_CONFIG_ENTRY = {
    CONF_NAME: "Home router",
    CONF_HOST: "0.0.0.0",
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_PORT: 8278,
    CONF_SSL: True,
    mikrotik_router.mikrotik_controller.CONF_SCAN_INTERVAL: 60,
    mikrotik_router.mikrotik_controller.CONF_UNIT_OF_MEASUREMENT: "Mbps",
    mikrotik_router.mikrotik_controller.CONF_TRACK_IFACE_CLIENTS: True,
    mikrotik_router.mikrotik_controller.CONF_TRACK_HOSTS: True,
    mikrotik_router.mikrotik_controller.CONF_TRACK_HOSTS_TIMEOUT: 180,
}


@pytest.fixture(name="api")
def mock_mikrotik_api():
    """Mock an api."""
    with patch("librouteros.connect"):
        yield


@pytest.fixture(name="auth_error")
def mock_api_authentication_error():
    """Mock an api."""
    with patch(
        "librouteros.connect",
        side_effect=librouteros.exceptions.TrapError("invalid user name or password"),
    ):
        yield


@pytest.fixture(name="conn_error")
def mock_api_connection_error():
    """Mock an api."""
    with patch(
        "librouteros.connect", side_effect=librouteros.exceptions.ConnectionClosed
    ):
        yield


async def test_import(hass, api):
    """Test import step."""
    result = await hass.config_entries.flow.async_init(
        mikrotik_router.DOMAIN, context={"source": "import"}, data=MOCK_DATA
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Mikrotik"
    assert result["data"][CONF_NAME] == "Mikrotik"
    assert result["data"][CONF_HOST] == "10.0.0.1"
    assert result["data"][CONF_USERNAME] == "admin"
    assert result["data"][CONF_PASSWORD] == "admin"
    assert result["data"][CONF_PORT] == 0
    assert result["data"][CONF_SSL] is False


async def test_flow_works(hass, api):
    """Test config flow."""

    result = await hass.config_entries.flow.async_init(
        mikrotik_router.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_USER_INPUT
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Home router"
    assert result["data"][CONF_NAME] == "Home router"
    assert result["data"][CONF_HOST] == "0.0.0.0"
    assert result["data"][CONF_USERNAME] == "username"
    assert result["data"][CONF_PASSWORD] == "password"
    assert result["data"][CONF_PORT] == 8278
    assert result["data"][CONF_SSL] is True


async def test_options(hass):
    """Test updating options."""
    entry = MockConfigEntry(domain=mikrotik_router.DOMAIN, data=DEMO_CONFIG_ENTRY)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "device_tracker"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mikrotik_router.mikrotik_controller.CONF_SCAN_INTERVAL: 30,
            mikrotik_router.mikrotik_controller.CONF_UNIT_OF_MEASUREMENT: "Kbps",
            mikrotik_router.mikrotik_controller.CONF_TRACK_IFACE_CLIENTS: True,
            mikrotik_router.mikrotik_controller.CONF_TRACK_HOSTS: False,
            mikrotik_router.mikrotik_controller.CONF_TRACK_HOSTS_TIMEOUT: 180,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        mikrotik_router.mikrotik_controller.CONF_SCAN_INTERVAL: 30,
        mikrotik_router.mikrotik_controller.CONF_UNIT_OF_MEASUREMENT: "Kbps",
        mikrotik_router.mikrotik_controller.CONF_TRACK_IFACE_CLIENTS: True,
        mikrotik_router.mikrotik_controller.CONF_TRACK_HOSTS: False,
        mikrotik_router.mikrotik_controller.CONF_TRACK_HOSTS_TIMEOUT: 180,
    }


async def test_name_exists(hass, api):
    """Test name already configured."""

    entry = MockConfigEntry(domain=mikrotik_router.DOMAIN, data=DEMO_CONFIG_ENTRY)
    entry.add_to_hass(hass)
    user_input = DEMO_USER_INPUT.copy()
    user_input[CONF_HOST] = "0.0.0.1"

    result = await hass.config_entries.flow.async_init(
        mikrotik_router.DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "name_exists"}


async def test_connection_error(hass, conn_error):
    """Test error when connection is unsuccessful."""

    result = await hass.config_entries.flow.async_init(
        mikrotik_router.DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_USER_INPUT
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"host": "cannot_connect"}


async def test_wrong_credentials(hass, auth_error):
    """Test error when credentials are wrong."""

    result = await hass.config_entries.flow.async_init(
        mikrotik_router.DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_USER_INPUT
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"host": "cannot_connect"}
