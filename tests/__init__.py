"""Tests for the Mikrotik Router component."""

from custom_components.mikrotik_router import config_flow

MOCK_DATA = {
    config_flow.CONF_NAME: config_flow.DEFAULT_DEVICE_NAME,
    config_flow.CONF_HOST: config_flow.DEFAULT_HOST,
    config_flow.CONF_USERNAME: config_flow.DEFAULT_USERNAME,
    config_flow.CONF_PASSWORD: config_flow.DEFAULT_PASSWORD,
    config_flow.CONF_PORT: config_flow.DEFAULT_PORT,
    config_flow.CONF_SSL: config_flow.DEFAULT_SSL,
}

MOCK_OPTIONS = {
    config_flow.CONF_SCAN_INTERVAL: config_flow.DEFAULT_SCAN_INTERVAL,
    config_flow.CONF_UNIT_OF_MEASUREMENT: config_flow.DEFAULT_UNIT_OF_MEASUREMENT,
    config_flow.CONF_TRACK_IFACE_CLIENTS: config_flow.DEFAULT_TRACK_IFACE_CLIENTS,
    config_flow.CONF_TRACK_HOSTS: config_flow.DEFAULT_TRACK_HOSTS,
    config_flow.CONF_TRACK_HOSTS_TIMEOUT: config_flow.DEFAULT_TRACK_HOST_TIMEOUT,
}
