"""Mikrotik Controller for Mikrotik Router."""

from datetime import timedelta
import logging
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
#from homeassistant.util import Throttle

from .const import (
	DOMAIN,
	CONF_TRACK_ARP,
	DEFAULT_TRACK_ARP,
	CONF_SCAN_INTERVAL,
	DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)
from .mikrotikapi import MikrotikAPI

#DEFAULT_SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

#---------------------------
#   MikrotikControllerData
#---------------------------
class MikrotikControllerData():
	def __init__(self, hass, config_entry, name, host, port, username, password, use_ssl):
		"""Initialize."""
		self.name = name
		self.hass = hass
		self.config_entry = config_entry
		
		self.data = {}
		self.data['routerboard'] = {}
		self.data['resource'] = {}
		self.data['interface'] = {}
		self.data['arp'] = {}
		
		self.listeners = []
		
		self.api = MikrotikAPI(host, username, password, port, use_ssl)
		if not self.api.connect():
			self.api = None
		
		async_track_time_interval(self.hass, self.force_update, self.option_scan_interval)
		
		return
	
	async def force_update(self, now=None):
		"""Periodic update."""
		await self.async_update()
		return
	
	#---------------------------
	#   option_track_arp
	#---------------------------
	@property
	def option_track_arp(self):
		"""Config entry option to not track ARP."""
		return self.config_entry.options.get(CONF_TRACK_ARP, DEFAULT_TRACK_ARP)
	
	#---------------------------
	#   option_scan_interval
	#---------------------------
	@property
	def option_scan_interval(self):
		"""Config entry option scan interval."""
		scan_interval = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
		return timedelta(seconds=scan_interval)
	
	#---------------------------
	#   signal_update
	#---------------------------
	@property
	def signal_update(self):
		"""Event specific per UniFi entry to signal new data."""
		return f"{DOMAIN}-update-{self.name}"
	
	#---------------------------
	#   connected
	#---------------------------
	def connected(self):
		"""Return connected boolean."""
		return self.api.connected()
	
	#---------------------------
	#   hwinfo_update
	#---------------------------
	async def hwinfo_update(self):
		"""Update Mikrotik hardware info."""
		self.get_system_routerboard()
		self.get_system_resource()
		return
	
	#---------------------------
	#   async_update
	#---------------------------
	#@Throttle(DEFAULT_SCAN_INTERVAL)
	async def async_update(self):
		"""Update Mikrotik Controller data."""
		
		self.get_interfaces()
		self.get_arp()
		
		async_dispatcher_send(self.hass, self.signal_update)
		return
	
	#---------------------------
	#   async_reset
	#---------------------------
	async def async_reset(self):
		"""Reset this controller to default state."""
		for unsub_dispatcher in self.listeners:
			unsub_dispatcher()
		
		self.listeners = []
		return True
	
	#---------------------------
	#   get_interfaces
	#---------------------------
	def get_interfaces(self):
		ifaces = self.api.path("/interface")
		for iface in ifaces:
			if 'default-name' not in iface:
				continue
			
			uid = iface['default-name']
			if uid not in self.data['interface']:
				self.data['interface'][uid] = {}
			
			self.data['interface'][uid]['default-name'] = iface['default-name']
			self.data['interface'][uid]['name'] = iface['name'] if 'name' in iface else iface['default-name']
			self.data['interface'][uid]['type'] = iface['type'] if 'type' in iface else "unknown"
			self.data['interface'][uid]['running'] = True if iface['running'] else False
			self.data['interface'][uid]['enabled'] = True if not iface['disabled'] else False
			self.data['interface'][uid]['port-mac-address'] = iface['mac-address'] if 'mac-address' in iface else ""
			self.data['interface'][uid]['comment'] = iface['comment'] if 'comment' in iface else ""
			self.data['interface'][uid]['last-link-down-time'] = iface['last-link-down-time'] if 'last-link-down-time' in iface else ""
			self.data['interface'][uid]['last-link-up-time'] = iface['last-link-up-time'] if 'last-link-up-time' in iface else ""
			self.data['interface'][uid]['link-downs'] = iface['link-downs'] if 'link-downs' in iface else ""
			self.data['interface'][uid]['rx-byte'] = iface['rx-byte'] if 'rx-byte' in iface else ""
			self.data['interface'][uid]['tx-byte'] = iface['tx-byte'] if 'tx-byte' in iface else ""
			self.data['interface'][uid]['tx-queue-drop'] = iface['tx-queue-drop'] if 'tx-queue-drop' in iface else ""
			self.data['interface'][uid]['actual-mtu'] = iface['actual-mtu'] if 'actual-mtu' in iface else ""
			
			if 'client-ip-address' not in self.data['interface'][uid]:
				self.data['interface'][uid]['client-ip-address'] = ""
			
			if 'client-mac-address' not in self.data['interface'][uid]:
				self.data['interface'][uid]['client-mac-address'] = ""
		
		return
	
	#---------------------------
	#   get_arp
	#---------------------------
	def get_arp(self):
		self.data['arp'] = {}
		if not self.option_track_arp:
			for uid in self.data['interface']:
				self.data['interface'][uid]['client-ip-address'] = "disabled"
				self.data['interface'][uid]['client-mac-address'] = "disabled"
			return False
		
		mac2ip = {}
		bridge_used = False
		data = self.api.path("/ip/arp")
		for entry in data:
			## Ignore invalid entries
			if entry['invalid']:
				continue
			
			## Do not add ARP detected on bridge
			if entry['interface'] == "bridge":
				bridge_used = True
				## Build address table on bridge
				if 'mac-address' in entry and 'address' in entry:
					mac2ip[entry['mac-address']] = entry['address']
				
				continue
			
			## Get iface default-name from custom name
			uid = None
			for ifacename in self.data['interface']:
				if self.data['interface'][ifacename]['name'] == entry['interface']:
					uid = self.data['interface'][ifacename]['default-name']
					break
			
			if not uid:
				continue
			
			## Create uid arp dict
			if uid not in self.data['arp']:
				self.data['arp'][uid] = {}
			
			## Add data
			self.data['arp'][uid]['interface'] = uid
			if 'mac-address' in self.data['arp'][uid]:
				self.data['arp'][uid]['mac-address'] = "multiple"
			else:
				self.data['arp'][uid]['mac-address'] = entry['mac-address'] if 'mac-address' in entry else ""
			
			if 'address' in self.data['arp'][uid]:
				self.data['arp'][uid]['address'] = "multiple"
			else:
				self.data['arp'][uid]['address'] = entry['address'] if 'address' in entry else ""
		
		if bridge_used:
			self.update_bridge_hosts(mac2ip)
		
		## Map ARP to ifaces
		for uid in self.data['interface']:
			self.data['interface'][uid]['client-ip-address'] = self.data['arp'][uid]['address'] if uid in self.data['arp'] and 'address' in self.data['arp'][uid] else ""
			self.data['interface'][uid]['client-mac-address'] = self.data['arp'][uid]['mac-address'] if uid in self.data['arp'] and 'mac-address' in self.data['arp'][uid] else ""
		
		return True
	
	#---------------------------
	#   update_bridge_hosts
	#---------------------------
	def update_bridge_hosts(self, mac2ip):
		data = self.api.path("/interface/bridge/host")
		for entry in data:
			## Ignore port MAC
			if entry['local']:
				continue
			
			## Get iface default-name from custom name
			uid = None
			for ifacename in self.data['interface']:
				if self.data['interface'][ifacename]['name'] == entry['interface']:
					uid = self.data['interface'][ifacename]['default-name']
					break
			
			if not uid:
				continue
			
			## Create uid arp dict
			if uid not in self.data['arp']:
				self.data['arp'][uid] = {}
			
			## Add data
			self.data['arp'][uid]['interface'] = uid
			if 'mac-address' in self.data['arp'][uid]:
				self.data['arp'][uid]['mac-address'] = "multiple"
				self.data['arp'][uid]['address'] = "multiple"
			else:
				self.data['arp'][uid]['mac-address'] = entry['mac-address'] if 'mac-address' in entry else ""
				self.data['arp'][uid]['address'] = ""
			
			if self.data['arp'][uid]['address'] == "" and self.data['arp'][uid]['mac-address'] in mac2ip:
				self.data['arp'][uid]['address'] = mac2ip[self.data['arp'][uid]['mac-address']]
		
		return
	
	#---------------------------
	#   get_system_routerboard
	#---------------------------
	def get_system_routerboard(self):
		data = self.api.path("/system/routerboard")
		for entry in data:
			self.data['routerboard']['routerboard'] = True if entry['routerboard'] else False
			self.data['routerboard']['model'] = entry['model'] if 'model' in entry else "unknown"
			self.data['routerboard']['serial-number'] = entry['serial-number'] if 'serial-number' in entry else "unknown"
			self.data['routerboard']['firmware'] = entry['current-firmware'] if 'current-firmware' in entry else "unknown"
		
		return
	
	#---------------------------
	#   get_system_resource
	#---------------------------
	def get_system_resource(self):
		data = self.api.path("/system/resource")
		for entry in data:
			self.data['resource']['platform'] = entry['platform'] if 'platform' in entry else "unknown"
			self.data['resource']['board-name'] = entry['board-name'] if 'board-name' in entry else "unknown"
			self.data['resource']['version'] = entry['version'] if 'version' in entry else "unknown"
		
		return
