"""Implementation of Mikrotik Router sensor entities."""

import logging

from typing import Any, Dict, Optional
from collections.abc import Mapping

from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    ATTR_ATTRIBUTION,
)

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.components.sensor import SensorEntity

from .const import (
    CONF_SENSOR_PORT_TRAFFIC,
    DEFAULT_SENSOR_PORT_TRAFFIC,
)

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, DATA_CLIENT, ATTRIBUTION
from .sensor_types import (
    MikrotikSensorEntityDescription,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   format_attribute
# ---------------------------
def format_attribute(attr):
    res = attr.replace("-", " ")
    res = res.capitalize()
    res = res.replace(" ip ", " IP ")
    res = res.replace(" mac ", " MAC ")
    res = res.replace(" mtu", " MTU")
    res = res.replace("Sfp", "SFP")
    res = res.replace("Poe", "POE")
    res = res.replace(" tx", " TX")
    res = res.replace(" rx", " RX")
    return res


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up device tracker for Mikrotik Router component."""
    inst = config_entry.data[CONF_NAME]
    mikrotik_controller = hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id]
    sensors = {}

    @callback
    def update_controller():
        """Update the values of the controller."""
        update_items(
            inst, config_entry, mikrotik_controller, async_add_entities, sensors
        )

    mikrotik_controller.listeners.append(
        async_dispatcher_connect(
            hass, mikrotik_controller.signal_update, update_controller
        )
    )

    update_controller()


# ---------------------------
#   update_items
# ---------------------------
@callback
def update_items(inst, config_entry, mikrotik_controller, async_add_entities, sensors):
    """Update sensor state from the controller."""
    new_sensors = []

    for sensor, sid_func in zip(
        # Data point name
        ["environment"],
        # Switch function
        [
            MikrotikControllerSensor,
        ],
    ):
        for uid in mikrotik_controller.data[sensor]:
            item_id = f"{inst}-{sensor}-{mikrotik_controller.data[sensor][uid][SENSOR_TYPES[sensor].data_uid]}"
            _LOGGER.debug("Updating sensor %s", item_id)
            if item_id in sensors:
                if sensors[item_id].enabled:
                    sensors[item_id].async_schedule_update_ha_state()
                continue

            sensors[item_id] = sid_func(
                inst=inst,
                uid=uid,
                mikrotik_controller=mikrotik_controller,
                entity_description=SENSOR_TYPES[sensor],
            )
            new_sensors.append(sensors[item_id])

    for sensor in SENSOR_TYPES:
        if sensor.startswith("system_"):
            if (
                SENSOR_TYPES[sensor].data_attribute
                not in mikrotik_controller.data[SENSOR_TYPES[sensor].data_path]
                or mikrotik_controller.data[SENSOR_TYPES[sensor].data_path][
                    SENSOR_TYPES[sensor].data_attribute
                ]
                == "unknown"
            ):
                continue
            item_id = f"{inst}-{sensor}"
            _LOGGER.debug("Updating sensor %s", item_id)
            if item_id in sensors:
                if sensors[item_id].enabled:
                    sensors[item_id].async_schedule_update_ha_state()
                continue

            sensors[item_id] = MikrotikControllerSensor(
                inst=inst,
                uid="",
                mikrotik_controller=mikrotik_controller,
                entity_description=SENSOR_TYPES[sensor],
            )
            new_sensors.append(sensors[item_id])

        if sensor.startswith("traffic_"):
            if not config_entry.options.get(
                CONF_SENSOR_PORT_TRAFFIC, DEFAULT_SENSOR_PORT_TRAFFIC
            ):
                continue

            for uid in mikrotik_controller.data["interface"]:
                if mikrotik_controller.data["interface"][uid]["type"] != "bridge":
                    item_id = f"{inst}-{sensor}-{mikrotik_controller.data['interface'][uid]['default-name']}"
                    _LOGGER.debug("Updating sensor %s", item_id)
                    if item_id in sensors:
                        if sensors[item_id].enabled:
                            sensors[item_id].async_schedule_update_ha_state()
                        continue

                    sensors[item_id] = MikrotikControllerSensor(
                        inst=inst,
                        mikrotik_controller=mikrotik_controller,
                        uid=uid,
                        entity_description=SENSOR_TYPES[sensor],
                    )
                    new_sensors.append(sensors[item_id])

        if sensor.startswith("client_traffic_"):
            for uid in mikrotik_controller.data["client_traffic"]:
                item_id = f"{inst}-{sensor}-{mikrotik_controller.data['client_traffic'][uid]['mac-address']}"
                if item_id in sensors:
                    if sensors[item_id].enabled:
                        sensors[item_id].async_schedule_update_ha_state()
                    continue

                if (
                    SENSOR_TYPES[sensor].data_attribute
                    in mikrotik_controller.data["client_traffic"][uid].keys()
                ):
                    sensors[item_id] = MikrotikClientTrafficSensor(
                        inst=inst,
                        mikrotik_controller=mikrotik_controller,
                        uid=uid,
                        entity_description=SENSOR_TYPES[sensor],
                    )
                    new_sensors.append(sensors[item_id])

    if new_sensors:
        async_add_entities(new_sensors, True)


# ---------------------------
#   MikrotikControllerSensor
# ---------------------------
class MikrotikControllerSensor(SensorEntity):
    """Define an Mikrotik Controller sensor."""

    def __init__(
        self,
        mikrotik_controller,
        inst,
        uid: "",
        entity_description: MikrotikSensorEntityDescription,
    ):
        """Initialize."""
        self.entity_description = entity_description
        self._inst = inst
        self._ctrl = mikrotik_controller
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self._uid = uid
        if self._uid:
            self._data = mikrotik_controller.data[self.entity_description.data_path][
                self._uid
            ]
        else:
            self._data = mikrotik_controller.data[self.entity_description.data_path]

    @property
    def name(self) -> str:
        """Return the name."""
        if self._uid:
            if self.entity_description.name:
                return f"{self._inst} {self._data[self.entity_description.data_name]} {self.entity_description.name}"

            return f"{self._inst} {self._data[self.entity_description.data_name]}"
        else:
            return f"{self._inst} {self.entity_description.name}"

    @property
    def unique_id(self) -> str:
        """Return a unique id for this entity."""
        if self._uid:
            return f"{self._inst.lower()}-{self.entity_description.key}-{self._data[self.entity_description.data_reference].lower()}"
        else:
            return f"{self._inst.lower()}-{self.entity_description.key}"

    @property
    def state(self) -> Optional[str]:
        """Return the state."""
        if self.entity_description.data_attribute:
            return self._data[self.entity_description.data_attribute]
        else:
            return "unknown"

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        if self.entity_description.native_unit_of_measurement:
            if self.entity_description.native_unit_of_measurement.startswith("data__"):
                uom = self.entity_description.native_unit_of_measurement[6:]
                if uom in self._data:
                    uom = self._data[uom]
                    return uom

            return self.entity_description.native_unit_of_measurement

        return None

    @property
    def available(self) -> bool:
        """Return if controller is available."""
        return self._ctrl.connected()

    @property
    def device_info(self) -> DeviceInfo:
        """Return a description for device registry."""
        dev_connection = DOMAIN
        dev_connection_value = self.entity_description.data_reference
        dev_name = self.entity_description.ha_group
        if self.entity_description.ha_group == "System":
            dev_name = self._ctrl.data["resource"]["board-name"]
            dev_connection_value = self._ctrl.data["routerboard"]["serial-number"]

        if self.entity_description.ha_group.startswith("data__"):
            dev_name = self.entity_description.ha_group[6:]
            if dev_name in self._data:
                dev_name = self._data[dev_name]
                dev_connection_value = dev_name

        if self.entity_description.ha_connection:
            dev_connection = self.entity_description.ha_connection

        if self.entity_description.ha_connection_value:
            dev_connection_value = self.entity_description.ha_connection_value
            if dev_connection_value.startswith("data__"):
                dev_connection_value = dev_connection_value[6:]
                dev_connection_value = self._data[dev_connection_value]

        info = DeviceInfo(
            connections={(dev_connection, f"{dev_connection_value}")},
            default_name=f"{self._inst} {dev_name}",
            model=f"{self._ctrl.data['resource']['board-name']}",
            manufacturer=f"{self._ctrl.data['resource']['platform']}",
            sw_version=f"{self._ctrl.data['resource']['version']}",
            configuration_url=f"http://{self._ctrl.config_entry.data[CONF_HOST]}",
            via_device=(DOMAIN, f"{self._ctrl.data['routerboard']['serial-number']}"),
        )

        if "mac-address" in self.entity_description.data_reference:
            info = DeviceInfo(
                connections={(dev_connection, f"{dev_connection_value}")},
                default_name=f"{self._data[self.entity_description.data_name]}",
                via_device=(
                    DOMAIN,
                    f"{self._ctrl.data['routerboard']['serial-number']}",
                ),
            )

            if "manufacturer" in self._data and self._data["manufacturer"] != "":
                info["manufacturer"] = self._data["manufacturer"]

        return info

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the state attributes."""
        attributes = super().extra_state_attributes
        for variable in self.entity_description.data_attributes_list:
            if variable in self._data:
                attributes[format_attribute(variable)] = self._data[variable]

        return attributes

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        _LOGGER.debug("New sensor %s (%s)", self._inst, self.unique_id)


# ---------------------------
#   MikrotikClientTrafficSensor
# ---------------------------
class MikrotikClientTrafficSensor(MikrotikControllerSensor):
    """Define an Mikrotik MikrotikClientTrafficSensor sensor."""

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{self._data[self.entity_description.data_name]} {self.entity_description.name}"

    @property
    def available(self) -> bool:
        """Return if controller and accounting feature in Mikrotik is available.
        Additional check for lan-tx/rx sensors
        """
        if self.entity_description.data_attribute in ["lan-tx", "lan-rx"]:
            return (
                self._ctrl.connected()
                and self._data["available"]
                and self._data["local_accounting"]
            )
        else:
            return self._ctrl.connected() and self._data["available"]
