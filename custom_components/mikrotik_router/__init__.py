"""Mikrotik Router integration."""

import logging

from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    DOMAIN,
    DATA_CLIENT,
)
from .mikrotik_controller import MikrotikControllerData

_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   async_setup
# ---------------------------
async def async_setup(hass, _config):
    """Set up configured Mikrotik Controller."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_CLIENT] = {}
    return True


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(hass, config_entry):
    """Set up Mikrotik Router as config entry."""
    mikrotik_controller = MikrotikControllerData(hass, config_entry)
    await mikrotik_controller.async_hwinfo_update()

    await mikrotik_controller.async_update()

    if not mikrotik_controller.data:
        raise ConfigEntryNotReady()

    await mikrotik_controller.async_init()
    hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = mikrotik_controller

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry,
                                                      "binary_sensor")
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry,
                                                      "device_tracker")
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "switch")
    )

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        manufacturer=mikrotik_controller.data["resource"]["platform"],
        model=mikrotik_controller.data["routerboard"]["model"],
        name=mikrotik_controller.data["routerboard"]["model"],
        sw_version=mikrotik_controller.data["resource"]["version"],
    )

    return True


# ---------------------------
#   async_unload_entry
# ---------------------------
async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    mikrotik_controller = hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id]
    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    await hass.config_entries.async_forward_entry_unload(config_entry,
                                                         "binary_sensor")
    await hass.config_entries.async_forward_entry_unload(config_entry,
                                                         "device_tracker")
    await hass.config_entries.async_forward_entry_unload(config_entry, "switch")
    await mikrotik_controller.async_reset()
    hass.data[DOMAIN][DATA_CLIENT].pop(config_entry.entry_id)
    return True
