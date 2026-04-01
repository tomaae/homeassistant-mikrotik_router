"""Mikrotik Router integration."""

from __future__ import annotations

import voluptuous as vol
import logging
from collections import deque

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry
from homeassistant.config_entries import ConfigEntry

from homeassistant.const import CONF_VERIFY_SSL

from .const import PLATFORMS, DOMAIN, DEFAULT_VERIFY_SSL
from .coordinator import MikrotikData, MikrotikCoordinator, MikrotikTrackerCoordinator

SCRIPT_SCHEMA = vol.Schema(
    {vol.Required("router"): cv.string, vol.Required("script"): cv.string}
)

WOL_SCHEMA = vol.Schema(
    {
        vol.Required("mac"): cv.string,
        vol.Optional("interface"): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)

# Ring buffer for diagnostics log capture
_LOG_BUFFER = deque(maxlen=1000)


class _RingBufferHandler(logging.Handler):
    """Logging handler that stores records in a ring buffer for diagnostics."""

    def __init__(self, buffer):
        super().__init__()
        self._buffer = buffer

    def emit(self, record):
        self._buffer.append(self.format(record))


_log_handler = _RingBufferHandler(_LOG_BUFFER)
_log_handler.setLevel(logging.DEBUG)
_log_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
)
_integration_logger = logging.getLogger("custom_components.mikrotik_router")
_integration_logger.addHandler(_log_handler)
_integration_logger.setLevel(logging.DEBUG)


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    _LOGGER.info(
        "Setting up Mikrotik Router integration for %s",
        config_entry.data.get("host", "unknown"),
    )
    coordinator = MikrotikCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()
    coordinatorTracker = MikrotikTrackerCoordinator(hass, config_entry, coordinator)
    await coordinatorTracker.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = MikrotikData(
        data_coordinator=coordinator,
        tracker_coordinator=coordinatorTracker,
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Register global WoL service once (shared across all config entries)
    if not hass.services.has_service(DOMAIN, "send_magic_packet"):

        async def async_send_magic_packet(call) -> None:
            """Send a WoL magic packet via all connected MikroTik routers."""
            mac = call.data["mac"]
            interface = call.data.get("interface")
            for entry_data in hass.data.get(DOMAIN, {}).values():
                success = await hass.async_add_executor_job(
                    entry_data.data_coordinator.api.wol, mac, interface
                )
                if not success:
                    _LOGGER.warning(
                        "WoL: failed to send magic packet to %s via router %s",
                        mac,
                        entry_data.data_coordinator.config_entry.data.get("host", "unknown"),
                    )

        hass.services.async_register(
            DOMAIN,
            "send_magic_packet",
            async_send_magic_packet,
            schema=WOL_SCHEMA,
        )

    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))

    return True


# ---------------------------
#   async_reload_entry
# ---------------------------
async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload the config entry when it changed."""
    await hass.config_entries.async_reload(config_entry.entry_id)


# ---------------------------
#   async_unload_entry
# ---------------------------
async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


# ---------------------------
#   async_remove_config_entry_device
# ---------------------------
async def async_remove_config_entry_device(
    hass, config_entry: ConfigEntry, device_entry: device_registry.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True


# ---------------------------
#   async_migrate_entry
# ---------------------------
async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version < 2:
        new_data = {**config_entry.data}
        new_data[CONF_VERIFY_SSL] = DEFAULT_VERIFY_SSL
        hass.config_entries.async_update_entry(config_entry, data=new_data, version=2)

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )
    return True
