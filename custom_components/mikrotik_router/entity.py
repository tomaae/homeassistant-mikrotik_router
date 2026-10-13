"""Mikrotik HA shared entity model"""

from __future__ import annotations

from collections.abc import Mapping
from logging import getLogger
from typing import Any, Callable, TypeVar

from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME, CONF_HOST, CONF_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    DOMAIN,
    ATTRIBUTION,
    CONF_SENSOR_PORT_TRAFFIC,
    DEFAULT_SENSOR_PORT_TRAFFIC,
    CONF_TRACK_HOSTS,
    DEFAULT_TRACK_HOSTS,
    CONF_SENSOR_PORT_TRACKER,
    DEFAULT_SENSOR_PORT_TRACKER,
    CONF_SENSOR_NETWATCH_TRACKER,
    DEFAULT_SENSOR_NETWATCH_TRACKER,
)
from .coordinator import (
    MikrotikConfigEntry,
    MikrotikCoordinator,
    MikrotikTrackerCoordinator,
)
from .exceptions import ApiEntryNotFound
from .helper import format_attribute

_LOGGER = getLogger(__name__)


def _skip_sensor(config_entry, entity_description, data, uid) -> bool:
    # Sensors
    if (
        entity_description.func == "MikrotikInterfaceTrafficSensor"
        and not config_entry.options.get(
            CONF_SENSOR_PORT_TRAFFIC, DEFAULT_SENSOR_PORT_TRAFFIC
        )
    ):
        return True

    if (
        entity_description.func == "MikrotikInterfaceTrafficSensor"
        and data[uid]["type"] == "bridge"
    ):
        return True

    if (
        entity_description.data_path == "client_traffic"
        and entity_description.data_attribute not in data[uid].keys()
    ):
        return True

    # Binary sensors
    if (
        entity_description.func == "MikrotikPortBinarySensor"
        and data[uid]["type"] == "wlan"
    ):
        return True

    if (
        entity_description.func == "MikrotikPortBinarySensor"
        and not config_entry.options.get(
            CONF_SENSOR_PORT_TRACKER, DEFAULT_SENSOR_PORT_TRACKER
        )
    ):
        return True

    if entity_description.data_path == "netwatch" and not config_entry.options.get(
        CONF_SENSOR_NETWATCH_TRACKER, DEFAULT_SENSOR_NETWATCH_TRACKER
    ):
        return True

    # Device Tracker
    if (
        # Skip if host tracking is disabled
        entity_description.func == "MikrotikHostDeviceTracker"
        and not config_entry.options.get(CONF_TRACK_HOSTS, DEFAULT_TRACK_HOSTS)
    ):
        return True

    return False


# ---------------------------
#   async_add_entities
# ---------------------------
async def async_add_entities(
    hass: HomeAssistant,
    config_entry: MikrotikConfigEntry,
    add_entities_callback: AddEntitiesCallback,
    dispatcher: dict[str, Callable],
    descriptions,
    services,
    coordinator=None,
):
    """Add entities."""
    if coordinator is None:
        coordinator = config_entry.runtime_data.data_coordinator

    known_unique_ids = set()

    @callback
    def async_update_controller():
        """Add entities discovered in the latest coordinator data."""
        if coordinator.data is None:
            return

        new_entities = []

        for entity_description in descriptions:
            data = coordinator.data.get(entity_description.data_path)
            if not isinstance(data, dict):
                continue

            if not entity_description.data_reference:
                if data.get(entity_description.data_attribute) is None:
                    continue
                uids = (None,)
            else:
                uids = tuple(data)

            for uid in uids:
                if uid is not None and _skip_sensor(
                    config_entry, entity_description, data, uid
                ):
                    continue

                obj = dispatcher[entity_description.func](
                    coordinator, entity_description, uid
                )
                if obj.unique_id in known_unique_ids:
                    continue

                known_unique_ids.add(obj.unique_id)
                new_entities.append(obj)

        if new_entities:
            add_entities_callback(new_entities)

    async_update_controller()
    config_entry.async_on_unload(
        coordinator.async_add_listener(async_update_controller)
    )


_MikrotikCoordinatorT = TypeVar(
    "_MikrotikCoordinatorT",
    bound=MikrotikCoordinator | MikrotikTrackerCoordinator,
)


# ---------------------------
#   MikrotikEntity
# ---------------------------
class MikrotikEntity(CoordinatorEntity[_MikrotikCoordinatorT], Entity):
    """Define entity"""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MikrotikCoordinator,
        entity_description,
        uid: str | None = None,
    ):
        """Initialize entity"""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._inst = coordinator.config_entry.data[CONF_NAME]
        self._config_entry = self.coordinator.config_entry
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self._uid = uid
        self._data = coordinator.data[self.entity_description.data_path]
        if self._uid:
            self._data = coordinator.data[self.entity_description.data_path][self._uid]

        self._attr_name = self.custom_name

    async def async_run_routeros(self, target: Callable[..., bool], *args) -> None:
        """Run a synchronous RouterOS command outside the event loop."""
        try:
            result = await self.hass.async_add_executor_job(target, *args)
        except ApiEntryNotFound as error:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_found",
                translation_placeholders={"entry": str(error)},
            ) from error
        except Exception as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="routeros_command_failed",
            ) from error

        if not result:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="routeros_command_failed",
            )

    def require_access(self, *permissions: str) -> None:
        """Raise when the configured RouterOS user lacks required access."""
        missing = [
            permission
            for permission in permissions
            if permission not in self.coordinator.data["access"]
        ]
        if missing:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="missing_permissions",
                translation_placeholders={"permissions": ", ".join(missing)},
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        path_data = data.get(self.entity_description.data_path) if data else None
        if isinstance(path_data, dict):
            if self._uid:
                if self._uid in path_data:
                    self._data = path_data[self._uid]
            elif path_data.get(self.entity_description.data_attribute) is not None:
                self._data = path_data
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return whether the coordinator and backing data are available."""
        if not super().available or self.coordinator.data is None:
            return False

        data = self.coordinator.data.get(self.entity_description.data_path)
        if not isinstance(data, dict):
            return False

        if self._uid:
            return self._uid in data

        return data.get(self.entity_description.data_attribute) is not None

    @property
    def custom_name(self) -> str:
        """Return the name for this entity"""
        if not self._uid:
            if self.entity_description.data_name_comment and self._data["comment"]:
                return f"{self._data['comment']}"

            return f"{self.entity_description.name}"

        if self.entity_description.data_name_comment and self._data["comment"]:
            return f"{self._data['comment']}"

        if self.entity_description.name:
            if (
                self._data[self.entity_description.data_reference]
                == self._data[self.entity_description.data_name]
            ):
                return f"{self.entity_description.name}"

            return f"{self._data[self.entity_description.data_name]} {self.entity_description.name}"

        return f"{self._data[self.entity_description.data_name]}"

    @property
    def unique_id(self) -> str:
        """Return a unique id for this entity"""
        return self._mikrotik_unique_id()

    def _mikrotik_unique_id(self) -> str:
        """Return the integration-specific unique ID."""
        if self._uid:
            return f"{self._inst.lower()}-{self.entity_description.key}-{slugify(str(self._data[self.entity_description.data_reference]).lower())}"

        return f"{self._inst.lower()}-{self.entity_description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return a description for device registry."""
        dev_connection = DOMAIN
        dev_connection_value = self.entity_description.data_reference
        dev_group = self.entity_description.ha_group
        if self.entity_description.ha_group == "System":
            dev_group = self.coordinator.data["resource"]["board-name"]
            dev_connection_value = self.coordinator.data["routerboard"]["serial-number"]

        if self.entity_description.ha_group.startswith("data__"):
            dev_group = self.entity_description.ha_group[6:]
            if dev_group in self._data:
                dev_group = self._data[dev_group]
                dev_connection_value = dev_group

        if self.entity_description.ha_connection:
            dev_connection = self.entity_description.ha_connection

        if self.entity_description.ha_connection_value:
            dev_connection_value = self.entity_description.ha_connection_value
            if dev_connection_value.startswith("data__"):
                dev_connection_value = dev_connection_value[6:]
                dev_connection_value = self._data[dev_connection_value]

        if self.entity_description.ha_group == "System":
            protocol = (
                "https" if self.coordinator.config_entry.data[CONF_SSL] else "http"
            )
            return DeviceInfo(
                connections={(dev_connection, f"{dev_connection_value}")},
                identifiers={(dev_connection, f"{dev_connection_value}")},
                name=f"{self._inst} {dev_group}",
                model=f"{self.coordinator.data['resource']['board-name']}",
                manufacturer=f"{self.coordinator.data['resource']['platform']}",
                sw_version=f"{self.coordinator.data['resource']['version']}",
                configuration_url=f"{protocol}://{self.coordinator.config_entry.data[CONF_HOST]}",
            )

        via_device_id = device_registry.async_get_device_id_by_identifier(
            self.hass,
            (
                DOMAIN,
                f"{self.coordinator.data['routerboard']['serial-number']}",
            ),
            config_entry_id=self._config_entry.entry_id,
        )

        if "mac-address" in self.entity_description.data_reference:
            dev_group = self._data[self.entity_description.data_name]
            dev_manufacturer = ""
            if dev_connection_value in self.coordinator.data["host"]:
                dev_group = self.coordinator.data["host"][dev_connection_value][
                    "host-name"
                ]
                dev_manufacturer = self.coordinator.data["host"][dev_connection_value][
                    "manufacturer"
                ]

            return DeviceInfo(
                connections={(dev_connection, f"{dev_connection_value}")},
                name=f"{dev_group}",
                manufacturer=f"{dev_manufacturer}",
                via_device_id=via_device_id,
            )
        else:
            return DeviceInfo(
                connections={(dev_connection, f"{dev_connection_value}")},
                name=f"{self._inst} {dev_group}",
                model=f"{self.coordinator.data['resource']['board-name']}",
                manufacturer=f"{self.coordinator.data['resource']['platform']}",
                via_device_id=via_device_id,
            )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the state attributes."""
        # A fresh dict, so attributes that left the data do not linger
        attributes = dict(super().extra_state_attributes)
        for variable in self.entity_description.data_attributes_list:
            if variable in self._data:
                attributes[format_attribute(variable)] = self._data[variable]

        return attributes

    async def start(self):
        """Dummy run function"""
        raise NotImplementedError()

    async def stop(self):
        """Dummy stop function"""
        raise NotImplementedError()

    async def restart(self):
        """Dummy restart function"""
        raise NotImplementedError()

    async def reload(self):
        """Dummy reload function"""
        raise NotImplementedError()
