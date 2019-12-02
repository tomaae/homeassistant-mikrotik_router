"""Support for the Mikrotik Router device tracker."""

import logging
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SOURCE_TYPE_ROUTER
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

DEVICE_ATTRIBUTES = [
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


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up device tracker for Mikrotik Router component."""
    name = config_entry.data[CONF_NAME]
    mikrotik_controller = hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id]
    tracked = {}
    
    @callback
    def update_controller():
        """Update the values of the controller."""
        update_items(name, mikrotik_controller, async_add_entities, tracked)
    
    mikrotik_controller.listeners.append(
        async_dispatcher_connect(hass, mikrotik_controller.signal_update, update_controller)
    )
    
    update_controller()
    return


# ---------------------------
#   update_items
# ---------------------------
@callback
def update_items(name, mikrotik_controller, async_add_entities, tracked):
    """Update tracked device state from the controller."""
    new_tracked = []
    
    for uid in mikrotik_controller.data['interface']:
        if mikrotik_controller.data['interface'][uid]['type'] == "ether":
            item_id = name + "-" + mikrotik_controller.data['interface'][uid]['default-name']
            if item_id in tracked:
                if tracked[item_id].enabled:
                    tracked[item_id].async_schedule_update_ha_state()
                continue
            
            tracked[item_id] = MikrotikControllerPortDeviceTracker(name, uid, mikrotik_controller)
            new_tracked.append(tracked[item_id])
    
    if new_tracked:
        async_add_entities(new_tracked)
    
    return


# ---------------------------
#   MikrotikControllerPortDeviceTracker
# ---------------------------
class MikrotikControllerPortDeviceTracker(ScannerEntity):
    """Representation of a network port."""
    
    def __init__(self, name, uid, mikrotik_controller):
        """Set up tracked port."""
        self._name = name
        self._uid = uid
        self.mikrotik_controller = mikrotik_controller
        
        self._attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }
    
    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        return True
    
    async def async_added_to_hass(self):
        """Port entity created."""
        _LOGGER.debug("New port tracker %s (%s)", self._name, self.mikrotik_controller.data['interface'][self._uid]['port-mac-address'])
        return
    
    async def async_update(self):
        """Synchronize state with controller."""
        # await self.mikrotik_controller.async_update()
        return
    
    @property
    def is_connected(self):
        """Return true if the port is connected to the network."""
        return self.mikrotik_controller.data['interface'][self._uid]['running']
    
    @property
    def source_type(self):
        """Return the source type of the port."""
        return SOURCE_TYPE_ROUTER
    
    @property
    def name(self) -> str:
        """Return the name of the port."""
        return self.mikrotik_controller.data['interface'][self._uid]['default-name']
    
    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this port."""
        return f"{self._name.lower()}-{self.mikrotik_controller.data['interface'][self._uid]['port-mac-address']}"
    
    @property
    def available(self) -> bool:
        """Return if controller is available."""
        return self.mikrotik_controller.connected()
    
    @property
    def icon(self):
        """Return the icon."""
        if not self.mikrotik_controller.data['interface'][self._uid]['enabled']:
            return 'mdi:lan-disconnect'
        
        if self.mikrotik_controller.data['interface'][self._uid]['running']:
            return 'mdi:lan-connect'
        else:
            return 'mdi:lan-pending'
    
    @property
    def device_info(self):
        """Return a port description for device registry."""
        info = {
            "connections": {(CONNECTION_NETWORK_MAC, self.mikrotik_controller.data['interface'][self._uid]['port-mac-address'])},
            "manufacturer": self.mikrotik_controller.data['resource']['platform'],
            "model": "Port",
            "name": self.mikrotik_controller.data['interface'][self._uid]['default-name'],
        }
        return info
    
    @property
    def device_state_attributes(self):
        """Return the port state attributes."""
        attributes = self._attrs
        
        for variable in DEVICE_ATTRIBUTES:
            if variable in self.mikrotik_controller.data['interface'][self._uid]:
                attributes[variable] = self.mikrotik_controller.data['interface'][self._uid][variable]
        
        return attributes
