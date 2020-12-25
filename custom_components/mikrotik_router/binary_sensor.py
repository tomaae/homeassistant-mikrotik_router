"""Support for the Mikrotik Router binary sensor service."""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    DEVICE_CLASS_CONNECTIVITY,
)
from homeassistant.const import (
    CONF_NAME,
    ATTR_ATTRIBUTION,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DOMAIN,
    DATA_CLIENT,
    ATTRIBUTION,
    CONF_SENSOR_PPP,
    DEFAULT_SENSOR_PPP,
)

_LOGGER = logging.getLogger(__name__)

ATTR_LABEL = "label"
ATTR_GROUP = "group"
ATTR_PATH = "data_path"
ATTR_ATTR = "data_attr"

SENSOR_TYPES = {
    "system_fwupdate": {
        ATTR_LABEL: "Firmware update",
        ATTR_GROUP: "System",
        ATTR_PATH: "fw-update",
        ATTR_ATTR: "available",
    },
}

DEVICE_ATTRIBUTES_PPP_SECRET = [
    "connected",
    "service",
    "profile",
    "comment",
    "caller-id",
    "encoding",
]


# ---------------------------
#   format_attribute
# ---------------------------
def format_attribute(attr):
    res = attr.replace("-", " ")
    res = res.capitalize()
    res = res.replace(" ip ", " IP ")
    res = res.replace(" mac ", " MAC ")
    res = res.replace(" mtu", " MTU")
    return res


# ---------------------------
#   format_value
# ---------------------------
def format_value(res):
    res = res.replace("dhcp", "DHCP")
    res = res.replace("dns", "DNS")
    res = res.replace("capsman", "CAPsMAN")
    res = res.replace("wireless", "Wireless")
    res = res.replace("restored", "Restored")
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

    # Add switches
    for sid, sid_uid, sid_name, sid_ref, sid_func in zip(
        # Data point name
        ["ppp_secret"],
        # Data point unique id
        ["name"],
        # Entry Name
        ["name"],
        # Entry Unique id
        ["name"],
        # Tracker function
        [
            MikrotikControllerPPPSecretBinarySensor,
        ],
    ):
        for uid in mikrotik_controller.data[sid]:
            # Update entity
            item_id = f"{inst}-{sid}-{mikrotik_controller.data[sid][uid][sid_uid]}"
            _LOGGER.debug("Updating binary_sensor %s", item_id)
            if item_id in sensors:
                if sensors[item_id].enabled:
                    sensors[item_id].async_schedule_update_ha_state()
                continue

            # Create new entity
            sid_data = {
                "sid": sid,
                "sid_uid": sid_uid,
                "sid_name": sid_name,
                "sid_ref": sid_ref,
            }
            sensors[item_id] = sid_func(
                inst, uid, mikrotik_controller, config_entry, sid_data
            )
            new_sensors.append(sensors[item_id])

    for sensor in SENSOR_TYPES:
        item_id = f"{inst}-{sensor}"
        _LOGGER.debug("Updating binary_sensor %s", item_id)
        if item_id in sensors:
            if sensors[item_id].enabled:
                sensors[item_id].async_schedule_update_ha_state()
            continue

        sensors[item_id] = MikrotikControllerBinarySensor(
            mikrotik_controller=mikrotik_controller, inst=inst, sensor=sensor
        )
        new_sensors.append(sensors[item_id])

    if new_sensors:
        async_add_entities(new_sensors, True)


class MikrotikControllerBinarySensor(BinarySensorEntity):
    """Define an Mikrotik Controller Binary Sensor."""

    def __init__(self, mikrotik_controller, inst, sensor):
        """Initialize."""
        self._inst = inst
        self._sensor = sensor
        self._ctrl = mikrotik_controller
        if sensor in SENSOR_TYPES:
            self._data = mikrotik_controller.data[SENSOR_TYPES[sensor][ATTR_PATH]]
            self._type = SENSOR_TYPES[sensor]
            self._attr = SENSOR_TYPES[sensor][ATTR_ATTR]

        self._device_class = None
        self._state = None
        self._icon = None
        self._unit_of_measurement = None
        self._attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def name(self):
        """Return the name."""
        return f"{self._inst} {self._type[ATTR_LABEL]}"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self._inst.lower()}-{self._sensor.lower()}"

    @property
    def available(self) -> bool:
        """Return if controller is available."""
        return self._ctrl.connected()

    @property
    def device_info(self):
        """Return a port description for device registry."""
        info = {
            "manufacturer": self._ctrl.data["resource"]["platform"],
            "model": self._ctrl.data["resource"]["board-name"],
            "name": f"{self._inst} {self._type[ATTR_GROUP]}",
        }
        if ATTR_GROUP in self._type:
            info["identifiers"] = {
                (
                    DOMAIN,
                    "serial-number",
                    self._ctrl.data["routerboard"]["serial-number"],
                    "switch",
                    self._type[ATTR_GROUP],
                )
            }

        return info

    async def async_update(self):
        """Synchronize state with controller."""

    async def async_added_to_hass(self):
        """Port entity created."""
        _LOGGER.debug("New sensor %s (%s)", self._inst, self._sensor)

    @property
    def is_on(self):
        """Return true if sensor is on."""
        val = False
        if self._attr in self._data:
            val = self._data[self._attr]

        return val


# ---------------------------
#   MikrotikControllerPPPSecretBinarySensor
# ---------------------------
class MikrotikControllerPPPSecretBinarySensor(MikrotikControllerBinarySensor):
    """Representation of a network device."""

    def __init__(self, inst, uid, mikrotik_controller, config_entry, sid_data):
        """Set up tracked port."""
        super().__init__(mikrotik_controller, inst, uid)
        self._sid_data = sid_data
        self._data = mikrotik_controller.data[self._sid_data["sid"]][uid]
        self._config_entry = config_entry

    @property
    def option_sensor_ppp(self):
        """Config entry option to not track ARP."""
        return self._config_entry.options.get(CONF_SENSOR_PPP, DEFAULT_SENSOR_PPP)

    @property
    def name(self):
        """Return the name of the port."""
        return f"{self._inst} PPP {self._data['name']}"

    @property
    def is_on(self):
        """Return true if the host is connected to the network."""
        if not self.option_sensor_ppp:
            return False

        return self._data["connected"]

    @property
    def device_class(self) -> str:
        """Return the device class."""
        return DEVICE_CLASS_CONNECTIVITY

    @property
    def available(self) -> bool:
        """Return if controller is available."""
        if not self.option_sensor_ppp:
            return False

        return self._ctrl.connected()

    @property
    def unique_id(self):
        """Return a unique identifier for this port."""
        return f"{self._inst.lower()}-{self._sid_data['sid']}_tracker-{self._data[self._sid_data['sid_ref']]}"

    @property
    def icon(self):
        """Return the icon."""
        if self._data["connected"]:
            return "mdi:account-network-outline"
        else:
            return "mdi:account-off-outline"

    @property
    def device_state_attributes(self):
        """Return the port state attributes."""
        attributes = self._attrs
        for variable in DEVICE_ATTRIBUTES_PPP_SECRET:
            if variable in self._data:
                attributes[format_attribute(variable)] = self._data[variable]

        return attributes

    @property
    def device_info(self):
        """Return a PPP Secret switch description for device registry."""
        info = {
            "identifiers": {
                (
                    DOMAIN,
                    "serial-number",
                    self._ctrl.data["routerboard"]["serial-number"],
                    "switch",
                    "PPP",
                )
            },
            "manufacturer": self._ctrl.data["resource"]["platform"],
            "model": self._ctrl.data["resource"]["board-name"],
            "name": f"{self._inst} PPP",
        }
        return info
