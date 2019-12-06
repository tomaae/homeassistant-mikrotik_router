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

_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   from_entry
# ---------------------------
def from_entry(entry, param, default=""):
    """Validate and return a value from a Mikrotik API dict"""
    if param not in entry:
        return default

    return entry[param]


# ---------------------------
#   from_entry_bool
# ---------------------------
def from_entry_bool(entry, param, default=False, reverse=False):
    """Validate and return a bool value from a Mikrotik API dict"""
    if param not in entry:
        return default

    if not reverse:
        ret = entry[param]
    else:
        if entry[param]:
            ret = False
        else:
            ret = True

    return ret


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

        self.get_firmare_update()

        async_dispatcher_send(self.hass, self.signal_update)
        return

    # ---------------------------
    #   async_update
    # ---------------------------
    async def async_update(self):
        """Update Mikrotik data"""

        if 'available' not in self.data['fw-update']:
            await self.async_fwupdate_check()

        self.get_interface()
        self.get_interface_client()
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
    def get_interface(self):
        """Get all interfaces data from Mikrotik"""
        data = self.api.path("/interface")
        for entry in data:
            if 'default-name' not in entry:
                continue

            uid = entry['default-name']
            if uid not in self.data['interface']:
                self.data['interface'][uid] = {}

            self.data['interface'][uid]['default-name'] = from_entry(entry, 'default-name')
            self.data['interface'][uid]['name'] = from_entry(entry, 'name', entry['default-name'])
            self.data['interface'][uid]['type'] = from_entry(entry, 'type', 'unknown')
            self.data['interface'][uid]['running'] = from_entry_bool(entry, 'running')
            self.data['interface'][uid]['enabled'] = from_entry_bool(entry, 'disabled', reverse=True)
            self.data['interface'][uid]['port-mac-address'] = from_entry(entry, 'mac-address')
            self.data['interface'][uid]['comment'] = from_entry(entry, 'comment')
            self.data['interface'][uid]['last-link-down-time'] = from_entry(entry, 'last-link-down-time')
            self.data['interface'][uid]['last-link-up-time'] = from_entry(entry, 'last-link-up-time')
            self.data['interface'][uid]['link-downs'] = from_entry(entry, 'link-downs')
            self.data['interface'][uid]['tx-queue-drop'] = from_entry(entry, 'tx-queue-drop')
            self.data['interface'][uid]['actual-mtu'] = from_entry(entry, 'actual-mtu')

            if 'client-ip-address' not in self.data['interface'][uid]:
                self.data['interface'][uid]['client-ip-address'] = ""

            if 'client-mac-address' not in self.data['interface'][uid]:
                self.data['interface'][uid]['client-mac-address'] = ""

        return

    # ---------------------------
    #   get_interface_client
    # ---------------------------
    def get_interface_client(self):
        """Get ARP data from Mikrotik"""
        self.data['arp'] = {}

        # Remove data if disabled
        if not self.option_track_arp:
            for uid in self.data['interface']:
                self.data['interface'][uid]['client-ip-address'] = "disabled"
                self.data['interface'][uid]['client-mac-address'] = "disabled"
            return False

        mac2ip = {}
        bridge_used = False
        mac2ip, bridge_used = self.update_arp(mac2ip, bridge_used)

        if bridge_used:
            self.update_bridge_hosts(mac2ip)

        # Map ARP to ifaces
        for uid in self.data['interface']:
            self.data['interface'][uid]['client-ip-address'] = self.data['arp'][uid]['address'] if uid in self.data['arp'] and 'address' in self.data['arp'][uid] else ""
            self.data['interface'][uid]['client-mac-address'] = self.data['arp'][uid]['mac-address'] if uid in self.data['arp'] and 'mac-address' in self.data['arp'][uid] else ""

        return True

    # ---------------------------
    #   update_arp
    # ---------------------------
    def update_arp(self, mac2ip, bridge_used):
        """Get list of hosts in ARP for interface client data from Mikrotik"""
        data = self.api.path("/ip/arp")
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
            uid = self.get_iface_from_entry(entry)
            if not uid:
                continue

            # Create uid arp dict
            if uid not in self.data['arp']:
                self.data['arp'][uid] = {}

            # Add data
            self.data['arp'][uid]['interface'] = uid
            self.data['arp'][uid]['mac-address'] = "multiple" if 'mac-address' in self.data['arp'][uid] else entry['mac-address']
            self.data['arp'][uid]['address'] = "multiple" if 'address' in self.data['arp'][uid] else entry['address']
        return mac2ip, bridge_used

    # ---------------------------
    #   update_bridge_hosts
    # ---------------------------
    def update_bridge_hosts(self, mac2ip):
        """Get list of hosts in bridge for interface client data from Mikrotik"""
        data = self.api.path("/interface/bridge/host")
        for entry in data:
            # Ignore port MAC
            if entry['local']:
                continue

            # Get iface default-name from custom name
            uid = self.get_iface_from_entry(entry)
            if not uid:
                continue

            # Create uid arp dict
            if uid not in self.data['arp']:
                self.data['arp'][uid] = {}

            # Add data
            self.data['arp'][uid]['interface'] = uid
            if 'mac-address' in self.data['arp'][uid]:
                self.data['arp'][uid]['mac-address'] = "multiple"
                self.data['arp'][uid]['address'] = "multiple"
            else:
                self.data['arp'][uid]['mac-address'] = entry['mac-address']
                self.data['arp'][uid]['address'] = ""

            if self.data['arp'][uid]['address'] == "" and self.data['arp'][uid]['mac-address'] in mac2ip:
                self.data['arp'][uid]['address'] = mac2ip[self.data['arp'][uid]['mac-address']]

        return

    # ---------------------------
    #   get_iface_from_entry
    # ---------------------------
    def get_iface_from_entry(self, entry):
        """Get interface name from Mikrotik"""
        uid = None
        for ifacename in self.data['interface']:
            if self.data['interface'][ifacename]['name'] == entry['interface']:
                uid = self.data['interface'][ifacename]['default-name']
                break

        return uid

    # ---------------------------
    #   get_nat
    # ---------------------------
    def get_nat(self):
        """Get NAT data from Mikrotik"""
        data = self.api.path("/ip/firewall/nat")
        for entry in data:
            if entry['action'] != 'dst-nat':
                continue

            uid = entry['.id']
            if uid not in self.data['nat']:
                self.data['nat'][uid] = {}

            self.data['nat'][uid]['name'] = entry['protocol'] + ':' + str(entry['dst-port'])
            self.data['nat'][uid]['protocol'] = from_entry(entry, 'protocol')
            self.data['nat'][uid]['dst-port'] = from_entry(entry, 'dst-port')
            self.data['nat'][uid]['in-interface'] = from_entry(entry, 'in-interface', 'any')
            self.data['nat'][uid]['to-addresses'] = from_entry(entry, 'to-addresses')
            self.data['nat'][uid]['to-ports'] = from_entry(entry, 'to-ports')
            self.data['nat'][uid]['comment'] = from_entry(entry, 'comment')
            self.data['nat'][uid]['enabled'] = from_entry_bool(entry, 'disabled', default=True, reverse=True)

        return

    # ---------------------------
    #   get_system_routerboard
    # ---------------------------
    def get_system_routerboard(self):
        """Get routerboard data from Mikrotik"""
        data = self.api.path("/system/routerboard")
        for entry in data:
            self.data['routerboard']['routerboard'] = from_entry_bool(entry, 'routerboard')
            self.data['routerboard']['model'] = from_entry(entry, 'model', 'unknown')
            self.data['routerboard']['serial-number'] = from_entry(entry, 'serial-number', 'unknown')
            self.data['routerboard']['firmware'] = from_entry(entry, 'current-firmware', 'unknown')

        return

    # ---------------------------
    #   get_system_resource
    # ---------------------------
    def get_system_resource(self):
        """Get system resources data from Mikrotik"""
        data = self.api.path("/system/resource")
        for entry in data:
            self.data['resource']['platform'] = from_entry(entry, 'platform', 'unknown')
            self.data['resource']['board-name'] = from_entry(entry, 'board-name', 'unknown')
            self.data['resource']['version'] = from_entry(entry, 'version', 'unknown')
            self.data['resource']['uptime'] = from_entry(entry, 'uptime', 'unknown')
            self.data['resource']['cpu-load'] = from_entry(entry, 'cpu-load', 'unknown')
            if 'free-memory' in entry and 'total-memory' in entry:
                self.data['resource']['memory-usage'] = round(((entry['total-memory'] - entry['free-memory']) / entry['total-memory']) * 100)
            else:
                self.data['resource']['memory-usage'] = "unknown"

            if 'free-hdd-space' in entry and 'total-hdd-space' in entry:
                self.data['resource']['hdd-usage'] = round(((entry['total-hdd-space'] - entry['free-hdd-space']) / entry['total-hdd-space']) * 100)
            else:
                self.data['resource']['hdd-usage'] = "unknown"

        return

    # ---------------------------
    #   get_system_routerboard
    # ---------------------------
    def get_firmare_update(self):
        """Check for firmware update on Mikrotik"""
        data = self.api.path("/system/package/update")
        for entry in data:
            self.data['fw-update']['available'] = True if entry['status'] == "New version is available" else False
            self.data['fw-update']['channel'] = from_entry(entry, 'channel', 'unknown')
            self.data['fw-update']['installed-version'] = from_entry(entry, 'installed-version', 'unknown')
            self.data['fw-update']['latest-version'] = from_entry(entry, 'latest-version', 'unknown')

        return

    # ---------------------------
    #   get_script
    # ---------------------------
    def get_script(self):
        """Get list of all scripts from Mikrotik"""
        data = self.api.path("/system/script")
        for entry in data:
            if 'name' not in entry:
                continue

            uid = entry['name']
            if uid not in self.data['script']:
                self.data['script'][uid] = {}

            self.data['script'][uid]['name'] = from_entry(entry, 'name')
            self.data['script'][uid]['last-started'] = from_entry(entry, 'last-started', 'unknown')
            self.data['script'][uid]['run-count'] = from_entry(entry, 'run-count', 'unknown')

        return
