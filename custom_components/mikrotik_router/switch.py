"""Support for the Mikrotik Router switches."""
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

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

DEVICE_ATTRIBUTES_IFACE = [
    "running",
    "enabled",
    "comment",
    "client-ip-address",
    "client-mac-address",
    "port-mac-address",
    "last-link-down-time",
    "last-link-up-time",
    "link-downs",
    "actual-mtu",
    "type",
    "name",
    "default-name",
]

DEVICE_ATTRIBUTES_NAT = [
    "protocol",
    "dst-port",
    "in-interface",
    "to-addresses",
    "to-ports",
    "comment",
]

DEVICE_ATTRIBUTES_SCRIPT = [
    "last-started",
    "run-count",
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
#   async_setup_entry
# ---------------------------
async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switches for Mikrotik Router component."""
    inst = config_entry.data[CONF_NAME]
    mikrotik_controller = hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id]
    switches = {}

    @callback
    def update_controller():
        """Update the values of the controller."""
        update_items(inst, mikrotik_controller, async_add_entities, switches)

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
def update_items(inst, mikrotik_controller, async_add_entities, switches):
    """Update device switch state from the controller."""
    new_switches = []

    # Add switches
    for sid, sid_func in zip(
        ["interface", "nat", "script"],
        [
            MikrotikControllerPortSwitch,
            MikrotikControllerNATSwitch,
            MikrotikControllerScriptSwitch,
        ],
    ):
        for uid in mikrotik_controller.data[sid]:
            item_id = f"{inst}-{sid}-{mikrotik_controller.data[sid][uid]['name']}"
            if item_id in switches:
                if switches[item_id].enabled:
                    switches[item_id].async_schedule_update_ha_state()
                continue

            switches[item_id] = sid_func(inst, uid, mikrotik_controller)
            new_switches.append(switches[item_id])

    if new_switches:
        async_add_entities(new_switches)


# ---------------------------
#   MikrotikControllerSwitch
# ---------------------------
class MikrotikControllerSwitch(SwitchDevice, RestoreEntity):
    """Representation of a switch."""

    def __init__(self, inst, uid, mikrotik_controller):
        """Set up switch."""
        self._inst = inst
        self._uid = uid
        self._ctrl = mikrotik_controller

    async def async_added_to_hass(self):
        """Switch entity created."""
        _LOGGER.debug("New switch %s (%s)", self._inst, self._uid)

    async def async_update(self):
        """Synchronize state with controller."""

    @property
    def available(self) -> bool:
        """Return if controller is available."""
        return self._ctrl.connected()


# ---------------------------
#   MikrotikControllerPortSwitch
# ---------------------------
class MikrotikControllerPortSwitch(MikrotikControllerSwitch):
    """Representation of a network port switch."""

    def __init__(self, inst, uid, mikrotik_controller):
        """Set up tracked port."""
        super().__init__(inst, uid, mikrotik_controller)

        self._data = mikrotik_controller.data["interface"][self._uid]
        self._attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    async def async_added_to_hass(self):
        """Port entity created."""
        _LOGGER.debug(
            "New port switch %s (%s %s)",
            self._inst,
            self._data["default-name"],
            self._data["port-mac-address"],
        )

    @property
    def name(self) -> str:
        """Return the name of the port."""
        return f"{self._inst} port {self._data['default-name']}"

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this port."""
        return f"{self._inst.lower()}-enable_switch-{self._data['port-mac-address']}"

    @property
    def icon(self):
        """Return the icon."""
        if self._data["running"]:
            icon = "mdi:lan-connect"
        else:
            icon = "mdi:lan-pending"

        if not self._data["enabled"]:
            icon = "mdi:lan-disconnect"

        return icon

    @property
    def device_info(self):
        """Return a port description for device registry."""
        info = {
            "connections": {(CONNECTION_NETWORK_MAC, self._data["port-mac-address"])},
            "manufacturer": self._ctrl.data["resource"]["platform"],
            "model": self._ctrl.data["resource"]["board-name"],
            "name": self._data["default-name"],
        }
        return info

    @property
    def device_state_attributes(self):
        """Return the port state attributes."""
        attributes = self._attrs

        for variable in DEVICE_ATTRIBUTES_IFACE:
            if variable in self._data:
                attributes[format_attribute(variable)] = self._data[variable]

        return attributes

    async def async_turn_on(self):
        """Turn on the switch."""
        path = "/interface"
        param = "default-name"
        value = self._data[param]
        mod_param = "disabled"
        mod_value = False
        self._ctrl.set_value(path, param, value, mod_param, mod_value)
        await self._ctrl.force_update()

    async def async_turn_off(self):
        """Turn on the switch."""
        path = "/interface"
        param = "default-name"
        value = self._data[param]
        mod_param = "disabled"
        mod_value = True
        self._ctrl.set_value(path, param, value, mod_param, mod_value)
        await self._ctrl.async_update()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._data["enabled"]


# ---------------------------
#   MikrotikControllerNATSwitch
# ---------------------------
class MikrotikControllerNATSwitch(MikrotikControllerSwitch):
    """Representation of a NAT switch."""

    def __init__(self, inst, uid, mikrotik_controller):
        """Set up NAT switch."""
        super().__init__(inst, uid, mikrotik_controller)

        self._data = mikrotik_controller.data["nat"][self._uid]
        self._attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    async def async_added_to_hass(self):
        """NAT switch entity created."""
        _LOGGER.debug("New port switch %s (%s)", self._inst, self._data["name"])

    @property
    def name(self) -> str:
        """Return the name of the NAT switch."""
        return f"{self._inst} NAT {self._data['name']}"

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this NAT switch."""
        return f"{self._inst.lower()}-nat_switch-{self._data['name']}"

    @property
    def icon(self):
        """Return the icon."""
        if not self._data["enabled"]:
            icon = "mdi:network-off-outline"
        else:
            icon = "mdi:network-outline"

        return icon

    @property
    def device_info(self):
        """Return a NAT switch description for device registry."""
        info = {
            "identifiers": {
                (
                    DOMAIN,
                    "serial-number",
                    self._ctrl.data["routerboard"]["serial-number"],
                    "switch",
                    "NAT",
                )
            },
            "manufacturer": self._ctrl.data["resource"]["platform"],
            "model": self._ctrl.data["resource"]["board-name"],
            "name": "NAT",
        }
        return info

    @property
    def device_state_attributes(self):
        """Return the NAT switch state attributes."""
        attributes = self._attrs

        for variable in DEVICE_ATTRIBUTES_NAT:
            if variable in self._data:
                attributes[format_attribute(variable)] = self._data[variable]

        return attributes

    async def async_turn_on(self):
        """Turn on the switch."""
        path = "/ip/firewall/nat"
        param = ".id"
        value = None
        for uid in self._ctrl.data["nat"]:
            if (
                self._ctrl.data["nat"][uid]["name"]
                == f"{self._data['protocol']}:{self._data['dst-port']}"
            ):
                value = self._ctrl.data["nat"][uid][".id"]

        mod_param = "disabled"
        mod_value = False
        self._ctrl.set_value(path, param, value, mod_param, mod_value)
        await self._ctrl.force_update()

    async def async_turn_off(self):
        """Turn on the switch."""
        path = "/ip/firewall/nat"
        param = ".id"
        value = None
        for uid in self._ctrl.data["nat"]:
            if (
                self._ctrl.data["nat"][uid]["name"]
                == f"{self._data['protocol']}:{self._data['dst-port']}"
            ):
                value = self._ctrl.data["nat"][uid][".id"]

        mod_param = "disabled"
        mod_value = True
        self._ctrl.set_value(path, param, value, mod_param, mod_value)
        await self._ctrl.async_update()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._data["enabled"]


# ---------------------------
#   MikrotikControllerScriptSwitch
# ---------------------------
class MikrotikControllerScriptSwitch(MikrotikControllerSwitch):
    """Representation of a script switch."""

    def __init__(self, inst, uid, mikrotik_controller):
        """Set up script switch."""
        super().__init__(inst, uid, mikrotik_controller)

        self._data = mikrotik_controller.data["script"][self._uid]
        self._attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    async def async_added_to_hass(self):
        """Script switch entity created."""
        _LOGGER.debug("New script switch %s (%s)", self._inst, self._data["name"])

    @property
    def name(self) -> str:
        """Return the name of the script switch."""
        return f"{self._inst} script {self._data['name']}"

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this script switch."""
        return f"{self._inst.lower()}-script_switch-{self._data['name']}"

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:script-text-outline"

    @property
    def device_info(self):
        """Return a script switch description for device registry."""
        info = {
            "identifiers": {
                (
                    DOMAIN,
                    "serial-number",
                    self._ctrl.data["routerboard"]["serial-number"],
                    "switch",
                    "Scripts",
                )
            },
            "manufacturer": self._ctrl.data["resource"]["platform"],
            "model": self._ctrl.data["resource"]["board-name"],
            "name": "Scripts",
        }
        return info

    @property
    def device_state_attributes(self):
        """Return the script switch state attributes."""
        attributes = self._attrs

        for variable in DEVICE_ATTRIBUTES_SCRIPT:
            if variable in self._data:
                attributes[format_attribute(variable)] = self._data[variable]

        return attributes

    async def async_turn_on(self):
        """Turn on the switch."""
        self._ctrl.run_script(self._data["name"])
        await self._ctrl.force_update()

    async def async_turn_off(self):
        """Turn off the switch."""

    @property
    def is_on(self):
        """Return true if device is on."""
        return False
