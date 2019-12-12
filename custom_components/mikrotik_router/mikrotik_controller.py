"""Mikrotik Controller for Mikrotik Router."""

from datetime import timedelta
import logging
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    CONF_TRACK_ARP,
    DEFAULT_TRACK_ARP,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)

from .mikrotikapi import MikrotikAPI
from .helper import from_entry, from_entry_bool, from_list

_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   MikrotikControllerData
# ---------------------------
class MikrotikControllerData():
    """MikrotikController Class"""
    def __init__(self, hass, config_entry, name, host, port, username, password, use_ssl):
        """Initialize MikrotikController."""
        self.name = name
        self.hass = hass
        self.config_entry = config_entry

        self.data = {'routerboard': {},
                     'resource': {},
                     'interface': {},
                     'arp': {},
                     'nat': {},
                     'fw-update': {},
                     'script': {}
                     }

        self.listeners = []

        self.api = MikrotikAPI(host, username, password, port, use_ssl)

        async_track_time_interval(self.hass, self.force_update, self.option_scan_interval)
        async_track_time_interval(self.hass, self.force_fwupdate_check, timedelta(hours=1))

        return

    # ---------------------------
    #   force_update
    # ---------------------------
    async def force_update(self, _now=None):
        """Trigger update by timer"""
        await self.async_update()
        return

    # ---------------------------
    #   force_fwupdate_check
    # ---------------------------
    async def force_fwupdate_check(self, _now=None):
        """Trigger hourly update by timer"""
        await self.async_fwupdate_check()
        return

    # ---------------------------
    #   option_track_arp
    # ---------------------------
    @property
    def option_track_arp(self):
        """Config entry option to not track ARP."""
        return self.config_entry.options.get(CONF_TRACK_ARP, DEFAULT_TRACK_ARP)

    # ---------------------------
    #   option_scan_interval
    # ---------------------------
    @property
    def option_scan_interval(self):
        """Config entry option scan interval."""
        scan_interval = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return timedelta(seconds=scan_interval)

    # ---------------------------
    #   signal_update
    # ---------------------------
    @property
    def signal_update(self):
        """Event to signal new data."""
        return "{}-update-{}".format(DOMAIN, self.name)

    # ---------------------------
    #   connected
    # ---------------------------
    def connected(self):
        """Return connected state"""
        return self.api.connected()

    # ---------------------------
    #   hwinfo_update
    # ---------------------------
    async def hwinfo_update(self):
        """Update Mikrotik hardware info"""
        self.get_system_routerboard()
        self.get_system_resource()
        return

    # ---------------------------
    #   async_fwupdate_check
    # ---------------------------
    async def async_fwupdate_check(self):
        """Update Mikrotik data"""

        self.get_firmware_update()

        async_dispatcher_send(self.hass, self.signal_update)
        return

    # ---------------------------
    #   async_update
    # ---------------------------
    async def async_update(self):
        """Update Mikrotik data"""

        if 'available' not in self.data['fw-update']:
            await self.async_fwupdate_check()

        await self.get_interface()
        await self.get_interface_traffic()
        await self.get_interface_client()
        self.get_nat()
        self.get_system_resource()
        self.get_script()

        async_dispatcher_send(self.hass, self.signal_update)
        return

    # ---------------------------
    #   async_reset
    # ---------------------------
    async def async_reset(self):
        """Reset dispatchers"""
        for unsub_dispatcher in self.listeners:
            unsub_dispatcher()

        self.listeners = []
        return True

    # ---------------------------
    #   set_value
    # ---------------------------
    def set_value(self, path, param, value, mod_param, mod_value):
        """Change value using Mikrotik API"""
        return self.api.update(path, param, value, mod_param, mod_value)

    # ---------------------------
    #   run_script
    # ---------------------------
    def run_script(self, name):
        """Run script using Mikrotik API"""
        return self.api.run_script(name)

    # ---------------------------
    #   get_interface
    # ---------------------------
    async def get_interface(self):
        """Get all interfaces data from Mikrotik"""
        self.data['interface'] = await from_list(
            data=self.data['interface'],
            source=await self.hass.async_add_executor_job(self.api.path, "/interface"),
            key='default-name',
            vals=[
                {'name': 'default-name'},
                {'name': 'name', 'default_val': 'default-name'},
                {'name': 'type', 'default': 'unknown'},
                {'name': 'running', 'type': 'bool'},
                {'name': 'enabled', 'source': 'disabled', 'type': 'bool', 'reverse': True},
                {'name': 'port-mac-address', 'source': 'mac-address'},
                {'name': 'comment'},
                {'name': 'last-link-down-time'},
                {'name': 'last-link-up-time'},
                {'name': 'link-downs'},
                {'name': 'tx-queue-drop'},
                {'name': 'actual-mtu'}
            ],
            ensure_vals=[
                {'name': 'client-ip-address'},
                {'name': 'client-mac-address'},
                {'name': 'rx-bits-per-second', 'default': 0},
                {'name': 'tx-bits-per-second', 'default': 0}
            ]
        )

        return

    # ---------------------------
    #   get_interface_traffic
    # ---------------------------
    async def get_interface_traffic(self):
        """Get traffic for all interfaces from Mikrotik"""
        interface_list = ""
        for uid in self.data['interface']:
            interface_list += self.data['interface'][uid]['name'] + ","

        interface_list = interface_list[:-1]

        self.data['interface'] = await from_list(
            data=self.data['interface'],
            source=await self.hass.async_add_executor_job(self.api.get_traffic, interface_list),
            key_search='name',
            vals=[
                {'name': 'rx-bits-per-second', 'default': 0},
                {'name': 'tx-bits-per-second', 'default': 0},
            ]
        )
        return

    # ---------------------------
    #   get_interface_client
    # ---------------------------
    async def get_interface_client(self):
        """Get ARP data from Mikrotik"""
        self.data['arp'] = {}

        # Remove data if disabled
        if not self.option_track_arp:
            for uid in self.data['interface']:
                self.data['interface'][uid]['client-ip-address'] = "disabled"
                self.data['interface'][uid]['client-mac-address'] = "disabled"
            return

        mac2ip = {}
        bridge_used = False
        mac2ip, bridge_used = await self.update_arp(mac2ip, bridge_used)

        if bridge_used:
            await self.update_bridge_hosts(mac2ip)

        # Map ARP to ifaces
        for uid in self.data['interface']:
            if uid not in self.data['arp']:
                continue

            self.data['interface'][uid]['client-ip-address'] = from_entry(self.data['arp'][uid], 'address')
            self.data['interface'][uid]['client-mac-address'] = from_entry(self.data['arp'][uid], 'mac-address')

        return

    # ---------------------------
    #   update_arp
    # ---------------------------
    async def update_arp(self, mac2ip, bridge_used):
        """Get list of hosts in ARP for interface client data from Mikrotik"""
        data = await self.hass.async_add_executor_job(self.api.path, "/ip/arp")
        if not data:
            return mac2ip, bridge_used

        for entry in data:
            # Ignore invalid entries
            if entry['invalid']:
                continue

            # Do not add ARP detected on bridge
            if entry['interface'] == "bridge":
                bridge_used = True
                # Build address table on bridge
                if 'mac-address' in entry and 'address' in entry:
                    mac2ip[entry['mac-address']] = entry['address']

                continue

            # Get iface default-name from custom name
            uid = await self.get_iface_from_entry(entry)
            if not uid:
                continue

            _LOGGER.debug("Processing entry {}, entry {}".format("/interface/bridge/host", entry))
            # Create uid arp dict
            if uid not in self.data['arp']:
                self.data['arp'][uid] = {}

            # Add data
            self.data['arp'][uid]['interface'] = uid
            self.data['arp'][uid]['mac-address'] = from_entry(entry, 'mac-address') if 'mac-address' not in self.data['arp'][uid] else "multiple"
            self.data['arp'][uid]['address'] = from_entry(entry, 'address') if 'address' not in self.data['arp'][uid] else "multiple"

        return mac2ip, bridge_used

    # ---------------------------
    #   update_bridge_hosts
    # ---------------------------
    async def update_bridge_hosts(self, mac2ip):
        """Get list of hosts in bridge for interface client data from Mikrotik"""
        data = await self.hass.async_add_executor_job(self.api.path, "/interface/bridge/host")
        if not data:
            return

        for entry in data:
            # Ignore port MAC
            if entry['local']:
                continue

            # Get iface default-name from custom name
            uid = await self.get_iface_from_entry(entry)
            if not uid:
                continue

            _LOGGER.debug("Processing entry {}, entry {}".format("/interface/bridge/host", entry))
            # Create uid arp dict
            if uid not in self.data['arp']:
                self.data['arp'][uid] = {}

            # Add data
            self.data['arp'][uid]['interface'] = uid
            if 'mac-address' in self.data['arp'][uid]:
                self.data['arp'][uid]['mac-address'] = "multiple"
                self.data['arp'][uid]['address'] = "multiple"
            else:
                self.data['arp'][uid]['mac-address'] = from_entry(entry, 'mac-address')
                self.data['arp'][uid]['address'] = mac2ip[self.data['arp'][uid]['mac-address']] if self.data['arp'][uid]['mac-address'] in mac2ip else ""

        return

    # ---------------------------
    #   get_iface_from_entry
    # ---------------------------
    async def get_iface_from_entry(self, entry):
        """Get interface default-name using name from interface dict"""
        uid = None
        for ifacename in self.data['interface']:
            if self.data['interface'][ifacename]['name'] == entry['interface']:
                uid = ifacename
                break

        return uid

    # ---------------------------
    #   get_nat
    # ---------------------------
    def get_nat(self):
        """Get NAT data from Mikrotik"""
        self.data['nat'] = await from_list(
            data=self.data['nat'],
            source=await self.hass.async_add_executor_job(self.api.path, "/ip/firewall/nat"),
            key='.id',
            vals=[
                {'name': '.id'},
                {'name': 'protocol'},
                {'name': 'dst-port'},
                {'name': 'in-interface', 'default': 'any'},
                {'name': 'to-addresses'},
                {'name': 'to-ports'},
                {'name': 'comment'},
                {'name': 'enabled', 'source': 'disabled', 'type': 'bool', 'reverse': True}
            ],
            val_proc=[
                [
                    {'name': 'name'},
                    {'action': 'combine'},
                    {'key': 'protocol'},
                    {'text': ':'},
                    {'key': 'dst-port'}
                ]
            ]
            only=[
                {'key': 'action', 'value': 'dst-nat'}
            ]
        )
        return

    # ---------------------------
    #   get_system_routerboard
    # ---------------------------
    def get_system_routerboard(self):
        """Get routerboard data from Mikrotik"""
        self.data['routerboard'] = await from_list(
            data=self.data['routerboard'],
            source=await self.hass.async_add_executor_job(self.api.path, "/system/routerboard"),
            vals=[
                {'name': 'routerboard', 'type': 'bool'},
                {'name': 'model', 'default': 'unknown'},
                {'name': 'serial-number', 'default': 'unknown'},
                {'name': 'firmware', 'default': 'unknown'},
            ]
        )
        return

    # ---------------------------
    #   get_system_resource
    # ---------------------------
    def get_system_resource(self):
        """Get system resources data from Mikrotik"""
        self.data['resource'] = await from_list(
            data=self.data['resource'],
            source=await self.hass.async_add_executor_job(self.api.path, "/system/resource"),
            vals=[
                {'name': 'platform', 'default': 'unknown'},
                {'name': 'board-name', 'default': 'unknown'},
                {'name': 'version', 'default': 'unknown'},
                {'name': 'uptime', 'default': 'unknown'},
                {'name': 'cpu-load', 'default': 'unknown'},
                {'name': 'free-memory', 'default': 0},
                {'name': 'total-memory', 'default': 0},
                {'name': 'free-hdd-space', 'default': 0},
                {'name': 'total-hdd-space', 'default': 0}
            ]
        )

        if entry['total-memory'] > 0:
            self.data['resource']['memory-usage'] = round(((entry['total-memory'] - entry['free-memory']) / entry['total-memory']) * 100)
        else:
            self.data['resource']['memory-usage'] = "unknown"

        if entry['total-hdd-space'] > 0:
            self.data['resource']['hdd-usage'] = round(((entry['total-hdd-space'] - entry['free-hdd-space']) / entry['total-hdd-space']) * 100)
        else:
            self.data['resource']['hdd-usage'] = "unknown"

        return

    # ---------------------------
    #   get_system_routerboard
    # ---------------------------
    def get_firmware_update(self):
        """Check for firmware update on Mikrotik"""
       self.data['fw-update'] = await from_list(
           data=self.data['fw-update'],
           source=await self.hass.async_add_executor_job(self.api.path, "/system/package/update"),
           vals=[
               {'name': 'status'},
               {'name': 'channel', 'default': 'unknown'},
               {'name': 'installed-version', 'default': 'unknown'},
               {'name': 'latest-version', 'default': 'unknown'}
           ]
       )

       if status in self.data['fw-update']:
           self.data['fw-update']['available'] = True if self.data['fw-update']['status'] == "New version is available" else False
       else:
           self.data['fw-update']['available'] = False
        
       return

    # ---------------------------
    #   get_script
    # ---------------------------
    def get_script(self):
        """Get list of all scripts from Mikrotik"""
        self.data['script'] = await from_list(
            data=self.data['script'],
            source=await self.hass.async_add_executor_job(self.api.path, "/system/script"),
            key='name',
            vals=[
                {'name': 'name'},
                {'name': 'last-started', 'default': 'unknown'},
                {'name': 'run-count', 'default': 'unknown'}
            ]
        )
        return
