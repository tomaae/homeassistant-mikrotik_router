"""Mikrotik Router integration."""

import logging
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.const import (
	CONF_NAME,
	CONF_HOST,
	CONF_PORT,
	CONF_USERNAME,
	CONF_PASSWORD,
	CONF_SSL,
)

from mikrotik_controller import MikrotikControllerData

from .const import (
	DOMAIN,
	DATA_CLIENT,
)

_LOGGER = logging.getLogger(__name__)


#---------------------------
#   async_setup
#---------------------------
async def async_setup(hass, config):
	"""Set up configured Mikrotik Controller."""
	hass.data[DOMAIN] = {}
	hass.data[DOMAIN][DATA_CLIENT] = {}
	return True


#---------------------------
#   async_setup_entry
#---------------------------
async def async_setup_entry(hass, config_entry):
	"""Set up Mikrotik Router as config entry."""
	name = config_entry.data[CONF_NAME]
	host = config_entry.data[CONF_HOST]
	port = config_entry.data[CONF_PORT]
	username = config_entry.data[CONF_USERNAME]
	password = config_entry.data[CONF_PASSWORD]
	use_ssl = config_entry.data[CONF_SSL]
	
	mikrotik_controller = MikrotikControllerData(hass, config_entry, name, host, port, username, password, use_ssl)
	await mikrotik_controller.hwinfo_update()
	await mikrotik_controller.async_update()
	
	if not mikrotik_controller.data:
		raise ConfigEntryNotReady()
	
	hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id] = mikrotik_controller
	
	#hass.async_create_task(
	#	hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
	#)
	
	hass.async_create_task(
		hass.config_entries.async_forward_entry_setup(config_entry, "device_tracker")
	)
	
	device_registry = await hass.helpers.device_registry.async_get_registry()
	device_registry.async_get_or_create(
		config_entry_id=config_entry.entry_id,
		manufacturer=mikrotik_controller.data['resource']['platform'],
		model=mikrotik_controller.data['routerboard']['model'],
		name=mikrotik_controller.data['routerboard']['model'],
		sw_version=mikrotik_controller.data['resource']['version'],
	)
	
	return True


#---------------------------
#   async_unload_entry
#---------------------------
async def async_unload_entry(hass, config_entry):
	"""Unload a config entry."""
	mikrotik_controller = hass.data[DOMAIN][DATA_CLIENT][config_entry.entry_id]
	await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
	await hass.config_entries.async_forward_entry_unload(config_entry, "device_tracker")
	await mikrotik_controller.async_reset()
	hass.data[DOMAIN][DATA_CLIENT].pop(config_entry.entry_id)
	return True
