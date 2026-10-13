"""Mikrotik Router integration."""

from __future__ import annotations

import voluptuous as vol
import logging

from homeassistant.components import zone
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.device_tracker.const import CONF_ASSOCIATED_ZONE
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.helpers.typing import ConfigType
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VERIFY_SSL,
    CONF_ZONE,
    STATE_HOME,
    Platform,
)
from homeassistant.util import slugify

from .const import PLATFORMS, DOMAIN, DEFAULT_VERIFY_SSL
from .coordinator import (
    MikrotikConfigEntry,
    MikrotikData,
    MikrotikCoordinator,
    MikrotikTrackerCoordinator,
)
from .helper import router_unique_id
from .binary_sensor_types import SENSOR_SERVICES as BINARY_SENSOR_SERVICES
from .button_types import SENSOR_SERVICES as BUTTON_SERVICES
from .device_tracker_types import SENSOR_SERVICES as DEVICE_TRACKER_SERVICES
from .sensor_types import SENSOR_SERVICES as SENSOR_PLATFORM_SERVICES
from .switch_types import SENSOR_SERVICES as SWITCH_SERVICES
from .update_types import SENSOR_SERVICES as UPDATE_SERVICES

SCRIPT_SCHEMA = vol.Schema(
    {vol.Required("router"): cv.string, vol.Required("script"): cv.string}
)

ENTITY_SERVICES = {
    Platform.BINARY_SENSOR: BINARY_SENSOR_SERVICES,
    Platform.BUTTON: BUTTON_SERVICES,
    Platform.DEVICE_TRACKER: DEVICE_TRACKER_SERVICES,
    Platform.SENSOR: SENSOR_PLATFORM_SERVICES,
    Platform.SWITCH: SWITCH_SERVICES,
    Platform.UPDATE: UPDATE_SERVICES,
}

_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   async_setup
# ---------------------------
async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up the Mikrotik Router integration."""
    registered_services = set()
    for entity_domain, entity_services in ENTITY_SERVICES.items():
        for service_name, schema, func in entity_services:
            if service_name in registered_services:
                continue

            service.async_register_platform_entity_service(
                hass,
                DOMAIN,
                service_name,
                entity_domain=entity_domain,
                schema=schema,
                func=func,
            )
            registered_services.add(service_name)

    return True


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(
    hass: HomeAssistant, config_entry: MikrotikConfigEntry
) -> bool:
    """Set up a config entry."""
    coordinator = MikrotikCoordinator(hass, config_entry)
    apis = [coordinator.api]

    async def _async_close_apis() -> None:
        """Close the RouterOS sockets on unload or failed setup."""
        for api in apis:
            await hass.async_add_executor_job(api.close)

    config_entry.async_on_unload(_async_close_apis)
    await coordinator.async_config_entry_first_refresh()
    _async_update_router_unique_id(hass, config_entry, coordinator)
    _async_setup_router_device(hass, config_entry, coordinator)
    coordinatorTracker = MikrotikTrackerCoordinator(hass, config_entry, coordinator)
    apis.append(coordinatorTracker.api)
    await coordinatorTracker.async_config_entry_first_refresh()
    config_entry.runtime_data = MikrotikData(
        data_coordinator=coordinator,
        tracker_coordinator=coordinatorTracker,
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))

    return True


# ---------------------------
#   _async_setup_router_device
# ---------------------------
def _async_setup_router_device(
    hass: HomeAssistant,
    config_entry: MikrotikConfigEntry,
    coordinator: MikrotikCoordinator,
) -> None:
    """Set up the router device before its child devices."""
    serial_number = f"{coordinator.data['routerboard']['serial-number']}"
    protocol = "https" if config_entry.data[CONF_SSL] else "http"
    device_registry.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(DOMAIN, serial_number)},
        identifiers={(DOMAIN, serial_number)},
        name=f"{config_entry.data[CONF_NAME]} {coordinator.data['resource']['board-name']}",
        model=f"{coordinator.data['resource']['board-name']}",
        manufacturer=f"{coordinator.data['resource']['platform']}",
        sw_version=f"{coordinator.data['resource']['version']}",
        configuration_url=f"{protocol}://{config_entry.data[CONF_HOST]}",
    )


# ---------------------------
#   _async_update_router_unique_id
# ---------------------------
def _async_update_router_unique_id(
    hass: HomeAssistant,
    config_entry: MikrotikConfigEntry,
    coordinator: MikrotikCoordinator,
) -> None:
    """Upgrade a fallback config-entry ID to a RouterBOARD serial."""
    if config_entry.unique_id and not config_entry.unique_id.startswith("endpoint:"):
        return

    unique_id = router_unique_id(
        config_entry.data[CONF_HOST],
        config_entry.data[CONF_PORT],
        config_entry.data[CONF_SSL],
        coordinator.ds["routerboard"].get("serial-number"),
    )
    if unique_id == config_entry.unique_id:
        return

    existing_entry = hass.config_entries.async_entry_for_domain_unique_id(
        DOMAIN, unique_id
    )
    if existing_entry and existing_entry.entry_id != config_entry.entry_id:
        _LOGGER.warning(
            "Mikrotik %s has the same RouterBOARD identifier as configuration %s; preserving both existing entries",
            config_entry.title,
            existing_entry.title,
        )
        return

    hass.config_entries.async_update_entry(config_entry, unique_id=unique_id)


# ---------------------------
#   async_reload_entry
# ---------------------------
async def async_reload_entry(
    hass: HomeAssistant, config_entry: MikrotikConfigEntry
) -> None:
    """Reload the config entry when it changed."""
    await hass.config_entries.async_reload(config_entry.entry_id)


# ---------------------------
#   async_unload_entry
# ---------------------------
async def async_unload_entry(
    hass: HomeAssistant, config_entry: MikrotikConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


# ---------------------------
#   async_remove_config_entry_device
# ---------------------------
async def async_remove_config_entry_device(
    hass, config_entry: MikrotikConfigEntry, device_entry: device_registry.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True


# ---------------------------
#   async_migrate_entry
# ---------------------------
def _legacy_zone_entity_id(hass: HomeAssistant, legacy_zone) -> str:
    """Convert the legacy integration-wide zone to a zone entity ID."""
    zone_name = str(legacy_zone or STATE_HOME).strip()
    normalized_zone_name = zone_name.casefold()

    if normalized_zone_name in (STATE_HOME, zone.ENTITY_ID_HOME):
        return zone.ENTITY_ID_HOME

    if normalized_zone_name.startswith(f"{zone.DOMAIN}."):
        return normalized_zone_name

    for zone_state in hass.states.async_all(zone.DOMAIN):
        if zone_state.name.casefold() == normalized_zone_name:
            return zone_state.entity_id

    return f"{zone.DOMAIN}.{slugify(zone_name)}"


def _async_migrate_device_tracker_zones(
    hass: HomeAssistant, config_entry: MikrotikConfigEntry, legacy_zone
) -> None:
    """Move the integration-wide zone to per-entity tracker options."""
    registry = entity_registry.async_get(hass)
    associated_zone = _legacy_zone_entity_id(hass, legacy_zone)

    for entry in entity_registry.async_entries_for_config_entry(
        registry, config_entry.entry_id
    ):
        if entry.domain != DEVICE_TRACKER_DOMAIN or entry.platform != DOMAIN:
            continue

        tracker_options = dict(entry.options.get(DEVICE_TRACKER_DOMAIN, {}))
        if CONF_ASSOCIATED_ZONE in tracker_options:
            continue

        tracker_options[CONF_ASSOCIATED_ZONE] = associated_zone
        registry.async_update_entity_options(
            entry.entity_id, DEVICE_TRACKER_DOMAIN, tracker_options
        )


def _async_migrate_temperature_sensor_units(
    hass: HomeAssistant, config_entry: MikrotikConfigEntry
) -> None:
    """Remove the integration-provided temperature display unit."""
    registry = entity_registry.async_get(hass)

    for entry in entity_registry.async_entries_for_config_entry(
        registry, config_entry.entry_id
    ):
        if (
            entry.domain != SENSOR_DOMAIN
            or entry.platform != DOMAIN
            or entry.original_device_class != SensorDeviceClass.TEMPERATURE
        ):
            continue

        if f"{SENSOR_DOMAIN}.private" in entry.options:
            registry.async_update_entity_options(
                entry.entity_id, f"{SENSOR_DOMAIN}.private", None
            )

        sensor_options = entry.options.get(SENSOR_DOMAIN, {})
        if CONF_UNIT_OF_MEASUREMENT not in sensor_options:
            registry.async_update_entity(entry.entity_id, unit_of_measurement=None)


async def async_migrate_entry(hass: HomeAssistant, config_entry: MikrotikConfigEntry):
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    new_data = {**config_entry.data}
    new_options = {**config_entry.options}
    new_version = config_entry.version
    new_minor_version = config_entry.minor_version
    new_unique_id = config_entry.unique_id

    if new_version < 2:
        new_data[CONF_VERIFY_SSL] = DEFAULT_VERIFY_SSL
        new_version = 2
        new_minor_version = 1

    if new_version == 2 and new_minor_version < 2:
        if new_unique_id is None:
            new_unique_id = router_unique_id(
                new_data[CONF_HOST],
                new_data[CONF_PORT],
                new_data[CONF_SSL],
            )
        new_minor_version = 2

    if new_version < 3:
        legacy_zone = new_options.get(CONF_ZONE, STATE_HOME)
        _async_migrate_device_tracker_zones(hass, config_entry, legacy_zone)
        new_options.pop(CONF_ZONE, None)
        new_version = 3
        new_minor_version = 1

    if new_version == 3 and new_minor_version < 2:
        new_minor_version = 2

    if new_version == 3 and new_minor_version < 3:
        _async_migrate_temperature_sensor_units(hass, config_entry)
        new_minor_version = 3

    if (
        new_data != config_entry.data
        or new_options != config_entry.options
        or new_version != config_entry.version
        or new_minor_version != config_entry.minor_version
        or new_unique_id != config_entry.unique_id
    ):
        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            options=new_options,
            unique_id=new_unique_id,
            version=new_version,
            minor_version=new_minor_version,
        )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )
    return True
