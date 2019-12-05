"""Support for the Mikrotik Router binary sensor service."""

import logging
from homeassistant.core import callback
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.const import (
    CONF_NAME,
    ATTR_ATTRIBUTION,
)

from .const import (
    DOMAIN,
    DATA_CLIENT,
    ATTRIBUTION,
)

_LOGGER = logging.getLogger(__name__)

ATTR_LABEL = "label"
ATTR_GROUP = "group"
ATTR_PATH = "data_path"
ATTR_ATTR = "data_attr"

SENSOR_TYPES = {
    'system_fwupdate': {
        ATTR_LABEL: 'Firmware update',
        ATTR_GROUP: "System",
        ATTR_PATH: "fw-update",
        ATTR_ATTR: "available",
    },
}


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up device tracker for Mikrotik Router component."""
    name = config_entry.data[CONF_NAME]
    mikrotik_controller = hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id]
    sensors = {}

    @callback
    def update_controller():
        """Update the values of the controller."""
        update_items(name, mikrotik_controller, async_add_entities, sensors)

    mikrotik_controller.listeners.append(
        async_dispatcher_connect(hass, mikrotik_controller.signal_update, update_controller)
    )

    update_controller()
    return


# ---------------------------
#   update_items
# ---------------------------
@callback
def update_items(name, mikrotik_controller, async_add_entities, sensors):
    """Update sensor state from the controller."""
    new_sensors = []

    for sensor in SENSOR_TYPES:
        item_id = name + "-" + sensor
        if item_id in sensors:
            if sensors[item_id].enabled:
                sensors[item_id].async_schedule_update_ha_state()
            continue

        sensors[item_id] = MikrotikControllerBinarySensor(mikrotik_controller=mikrotik_controller, name=name, kind=sensor)
        new_sensors.append(sensors[item_id])

    if new_sensors:
        async_add_entities(new_sensors, True)

    return


class MikrotikControllerBinarySensor(BinarySensorDevice):
    """Define an Mikrotik Controller Binary Sensor."""

    def __init__(self, mikrotik_controller, name, kind, uid=''):
        """Initialize."""
        self.mikrotik_controller = mikrotik_controller
        self._name = name
        self.kind = kind
        self.uid = uid

        self._device_class = None
        self._state = None
        self._icon = None
        self._unit_of_measurement = None
        self._attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def name(self):
        """Return the name."""
        if self.uid:
            return f"{self._name} {self.uid} {SENSOR_TYPES[self.kind][ATTR_LABEL]}"
        return f"{self._name} {SENSOR_TYPES[self.kind][ATTR_LABEL]}"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        if self.uid:
            return f"{self._name.lower()}-{self.kind.lower()}-{self.uid.lower()}"
        return f"{self._name.lower()}-{self.kind.lower()}"

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self.mikrotik_controller.data)

    @property
    def device_info(self):
        """Return a port description for device registry."""
        info = {
            "identifiers": {(DOMAIN, "serial-number", self.mikrotik_controller.data['routerboard']['serial-number'], "switch", "PORT")},
            "manufacturer": self.mikrotik_controller.data['resource']['platform'],
            "model": self.mikrotik_controller.data['resource']['board-name'],
            "name": SENSOR_TYPES[self.kind][ATTR_GROUP],
        }
        return info

    async def async_update(self):
        """Synchronize state with controller."""
        # await self.mikrotik_controller.async_update()
        return

    async def async_added_to_hass(self):
        """Port entity created."""
        _LOGGER.debug("New sensor %s (%s)", self._name, self.kind)
        return

    @property
    def is_on(self):
        """Return true if sensor is on."""
        val = False
        if SENSOR_TYPES[self.kind][ATTR_PATH] in self.mikrotik_controller.data and SENSOR_TYPES[self.kind][ATTR_ATTR] in self.mikrotik_controller.data[SENSOR_TYPES[self.kind][ATTR_PATH]]:
            val = self.mikrotik_controller.data[SENSOR_TYPES[self.kind][ATTR_PATH]][SENSOR_TYPES[self.kind][ATTR_ATTR]]

        return val
