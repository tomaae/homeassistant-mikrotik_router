"""Mikrotik Controller for Mikrotik Router."""

import asyncio
import logging
from datetime import timedelta
from ipaddress import ip_address, IPv4Network

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    CONF_TRACK_ARP,
    DEFAULT_TRACK_ARP,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_OF_MEASUREMENT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TRAFFIC_TYPE,
)
from .exceptions import ApiEntryNotFound
from .helper import from_entry, parse_api
from .mikrotikapi import MikrotikAPI

_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   MikrotikControllerData
# ---------------------------
class MikrotikControllerData:
    """MikrotikController Class"""

    def __init__(
        self,
        hass,
        config_entry,
        name,
        host,
        port,
        username,
        password,
        use_ssl,
        traffic_type,
    ):
        """Initialize MikrotikController."""
        self.name = name
        self.hass = hass
        self.host = host
        self.config_entry = config_entry
        self.traffic_type = traffic_type

        self.data = {
            "routerboard": {},
            "resource": {},
            "interface": {},
            "arp": {},
            "nat": {},
            "fw-update": {},
            "script": {},
            "queue": {},
            "dhcp-server": {},
            "dhcp": {},
            "accounting": {}
        }

        self.local_dhcp_networks = []

        self.listeners = []
        self.lock = asyncio.Lock()

        self.api = MikrotikAPI(host, username, password, port, use_ssl)

        self.raw_arp_entries = []
        self.nat_removed = {}

        async_track_time_interval(
            self.hass, self.force_update, self.option_scan_interval
        )
        async_track_time_interval(
            self.hass, self.force_fwupdate_check, timedelta(hours=1)
        )

    def _get_traffic_type_and_div(self):
        traffic_type = self.option_traffic_type
        if traffic_type == "Kbps":
            traffic_div = 0.001
        elif traffic_type == "Mbps":
            traffic_div = 0.000001
        elif traffic_type == "B/s":
            traffic_div = 0.125
        elif traffic_type == "KB/s":
            traffic_div = 0.000125
        elif traffic_type == "MB/s":
            traffic_div = 0.000000125
        else:
            traffic_type = "bps"
            traffic_div = 1
        return traffic_type, traffic_div

    # ---------------------------
    #   force_update
    # ---------------------------
    @callback
    async def force_update(self, _now=None):
        """Trigger update by timer"""
        await self.async_update()

    # ---------------------------
    #   force_fwupdate_check
    # ---------------------------
    @callback
    async def force_fwupdate_check(self, _now=None):
        """Trigger hourly update by timer"""
        await self.async_fwupdate_check()

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
        scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return timedelta(seconds=scan_interval)

    # ---------------------------
    #   option_traffic_type
    # ---------------------------
    @property
    def option_traffic_type(self):
        """Config entry option to not track ARP."""
        return self.config_entry.options.get(
            CONF_UNIT_OF_MEASUREMENT, DEFAULT_TRAFFIC_TYPE
        )

    # ---------------------------
    #   signal_update
    # ---------------------------
    @property
    def signal_update(self):
        """Event to signal new data."""
        return f"{DOMAIN}-update-{self.name}"

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
        try:
            await asyncio.wait_for(self.lock.acquire(), timeout=10)
        except:
            return

        await self.hass.async_add_executor_job(self.get_system_routerboard)
        await self.hass.async_add_executor_job(self.get_system_resource)
        self.lock.release()

    # ---------------------------
    #   async_fwupdate_check
    # ---------------------------
    async def async_fwupdate_check(self):
        """Update Mikrotik data"""
        await self.hass.async_add_executor_job(self.get_firmware_update)
        async_dispatcher_send(self.hass, self.signal_update)

    # ---------------------------
    #   async_update
    # ---------------------------
    async def async_update(self):
        """Update Mikrotik data"""
        try:
            await asyncio.wait_for(self.lock.acquire(), timeout=10)
        except:
            return

        if "available" not in self.data["fw-update"]:
            await self.async_fwupdate_check()

        await self.hass.async_add_executor_job(self.get_interface)
        await self.hass.async_add_executor_job(self.get_interface_traffic)
        await self.hass.async_add_executor_job(self.get_interface_client)
        await self.hass.async_add_executor_job(self.get_nat)
        await self.hass.async_add_executor_job(self.get_system_resource)
        await self.hass.async_add_executor_job(self.get_script)
        await self.hass.async_add_executor_job(self.get_queue)
        await self.hass.async_add_executor_job(self.get_dhcp)
        await self.hass.async_add_executor_job(self.get_accounting)

        async_dispatcher_send(self.hass, self.signal_update)
        self.lock.release()

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
        try:
            self.api.run_script(name)
        except ApiEntryNotFound as error:
            _LOGGER.error("Failed to run script: %s", error)

    # ---------------------------
    #   get_interface
    # ---------------------------
    def get_interface(self):
        """Get all interfaces data from Mikrotik"""
        self.data["interface"] = parse_api(
            data=self.data["interface"],
            source=self.api.path("/interface"),
            key="default-name",
            vals=[
                {"name": "default-name"},
                {"name": "name", "default_val": "default-name"},
                {"name": "type", "default": "unknown"},
                {"name": "running", "type": "bool"},
                {
                    "name": "enabled",
                    "source": "disabled",
                    "type": "bool",
                    "reverse": True,
                },
                {"name": "port-mac-address", "source": "mac-address"},
                {"name": "comment"},
                {"name": "last-link-down-time"},
                {"name": "last-link-up-time"},
                {"name": "link-downs"},
                {"name": "tx-queue-drop"},
                {"name": "actual-mtu"},
            ],
            ensure_vals=[
                {"name": "client-ip-address"},
                {"name": "client-mac-address"},
                {"name": "rx-bits-per-second", "default": 0},
                {"name": "tx-bits-per-second", "default": 0},
            ],
        )

    # ---------------------------
    #   get_interface_traffic
    # ---------------------------
    def get_interface_traffic(self):
        """Get traffic for all interfaces from Mikrotik"""
        interface_list = ""
        for uid in self.data["interface"]:
            interface_list += self.data["interface"][uid]["name"] + ","

        interface_list = interface_list[:-1]

        self.data["interface"] = parse_api(
            data=self.data["interface"],
            source=self.api.get_traffic(interface_list),
            key_search="name",
            vals=[
                {"name": "rx-bits-per-second", "default": 0},
                {"name": "tx-bits-per-second", "default": 0},
            ],
        )

        traffic_type, traffic_div = self._get_traffic_type_and_div()

        for uid in self.data["interface"]:
            self.data["interface"][uid][
                "rx-bits-per-second-attr"] = traffic_type
            self.data["interface"][uid][
                "tx-bits-per-second-attr"] = traffic_type
            self.data["interface"][uid]["rx-bits-per-second"] = round(
                self.data["interface"][uid]["rx-bits-per-second"] * traffic_div
            )
            self.data["interface"][uid]["tx-bits-per-second"] = round(
                self.data["interface"][uid]["tx-bits-per-second"] * traffic_div
            )

    # ---------------------------
    #   get_interface_client
    # ---------------------------
    def get_interface_client(self):
        """Get ARP data from Mikrotik"""
        self.data["arp"] = {}

        # Remove data if disabled
        if not self.option_track_arp:
            for uid in self.data["interface"]:
                self.data["interface"][uid]["client-ip-address"] = "disabled"
                self.data["interface"][uid]["client-mac-address"] = "disabled"
            return

        mac2ip = {}
        bridge_used = False
        mac2ip, bridge_used = self.update_arp(mac2ip, bridge_used)

        if bridge_used:
            self.update_bridge_hosts(mac2ip)

        # Map ARP to ifaces
        for uid in self.data["interface"]:
            if uid not in self.data["arp"]:
                continue

            self.data["interface"][uid]["client-ip-address"] = from_entry(
                self.data["arp"][uid], "address"
            )
            self.data["interface"][uid]["client-mac-address"] = from_entry(
                self.data["arp"][uid], "mac-address"
            )

    # ---------------------------
    #   update_arp
    # ---------------------------
    def update_arp(self, mac2ip, bridge_used):
        """Get list of hosts in ARP for interface client data from Mikrotik"""
        data = self.api.path("/ip/arp")
        self.raw_arp_entries = data
        if not data:
            return mac2ip, bridge_used

        for entry in data:
            # Ignore invalid entries
            if entry["invalid"]:
                continue

            if "interface" not in entry:
                continue

            # Do not add ARP detected on bridge
            if entry["interface"] == "bridge":
                bridge_used = True
                # Build address table on bridge
                if "mac-address" in entry and "address" in entry:
                    mac2ip[entry["mac-address"]] = entry["address"]

                continue

            # Get iface default-name from custom name
            uid = self.get_iface_from_entry(entry)
            if not uid:
                continue

            _LOGGER.debug("Processing entry %s, entry %s", "/ip/arp", entry)
            # Create uid arp dict
            if uid not in self.data["arp"]:
                self.data["arp"][uid] = {}

            # Add data
            self.data["arp"][uid]["interface"] = uid
            self.data["arp"][uid]["mac-address"] = (
                from_entry(entry, "mac-address") if "mac-address" not in self.data["arp"][uid] else "multiple"
            )
            self.data["arp"][uid]["address"] = (
                from_entry(entry, "address") if "address" not in self.data["arp"][uid] else "multiple"
            )

        return mac2ip, bridge_used

    # ---------------------------
    #   update_bridge_hosts
    # ---------------------------
    def update_bridge_hosts(self, mac2ip):
        """Get list of hosts in bridge for interface client data from Mikrotik"""
        data = self.api.path("/interface/bridge/host")
        if not data:
            return

        for entry in data:
            # Ignore port MAC
            if entry["local"]:
                continue

            # Get iface default-name from custom name
            uid = self.get_iface_from_entry(entry)
            if not uid:
                continue

            _LOGGER.debug(
                "Processing entry %s, entry %s", "/interface/bridge/host", entry
            )
            # Create uid arp dict
            if uid not in self.data["arp"]:
                self.data["arp"][uid] = {}

            # Add data
            self.data["arp"][uid]["interface"] = uid
            if "mac-address" in self.data["arp"][uid]:
                self.data["arp"][uid]["mac-address"] = "multiple"
                self.data["arp"][uid]["address"] = "multiple"
            else:
                self.data["arp"][uid]["mac-address"] = from_entry(entry,
                                                                  "mac-address")
                self.data["arp"][uid]["address"] = (
                    mac2ip[self.data["arp"][uid]["mac-address"]]
                    if self.data["arp"][uid]["mac-address"] in mac2ip
                    else ""
                )

    # ---------------------------
    #   get_iface_from_entry
    # ---------------------------
    def get_iface_from_entry(self, entry):
        """Get interface default-name using name from interface dict"""
        uid = None
        for ifacename in self.data["interface"]:
            if self.data["interface"][ifacename]["name"] == entry["interface"]:
                uid = ifacename
                break

        return uid

    # ---------------------------
    #   get_nat
    # ---------------------------
    def get_nat(self):
        """Get NAT data from Mikrotik"""
        self.data["nat"] = parse_api(
            data=self.data["nat"],
            source=self.api.path("/ip/firewall/nat"),
            key=".id",
            vals=[
                {"name": ".id"},
                {"name": "protocol", "default": "any"},
                {"name": "dst-port", "default": "any"},
                {"name": "in-interface", "default": "any"},
                {"name": "to-addresses"},
                {"name": "to-ports"},
                {"name": "comment"},
                {
                    "name": "enabled",
                    "source": "disabled",
                    "type": "bool",
                    "reverse": True,
                },
            ],
            val_proc=[
                [
                    {"name": "name"},
                    {"action": "combine"},
                    {"key": "protocol"},
                    {"text": ":"},
                    {"key": "dst-port"},
                ]
            ],
            only=[{"key": "action", "value": "dst-nat"}],
        )

        nat_uniq = {}
        nat_del = {}
        for uid in self.data["nat"]:
            tmp_name = self.data["nat"][uid]["name"]
            if tmp_name not in nat_uniq:
                nat_uniq[tmp_name] = uid
            else:
                nat_del[uid] = 1
                nat_del[nat_uniq[tmp_name]] = 1

        for uid in nat_del:
            if self.data["nat"][uid]["name"] not in self.nat_removed:
                self.nat_removed[self.data["nat"][uid]["name"]] = 1
                _LOGGER.error("Mikrotik %s duplicate NAT rule %s, entity will be unavailable.",
                              self.host, self.data["nat"][uid]["name"])

            del self.data["nat"][uid]

    # ---------------------------
    #   get_system_routerboard
    # ---------------------------
    def get_system_routerboard(self):
        """Get routerboard data from Mikrotik"""
        self.data["routerboard"] = parse_api(
            data=self.data["routerboard"],
            source=self.api.path("/system/routerboard"),
            vals=[
                {"name": "routerboard", "type": "bool"},
                {"name": "model", "default": "unknown"},
                {"name": "serial-number", "default": "unknown"},
                {"name": "firmware", "default": "unknown"},
            ],
        )

    # ---------------------------
    #   get_system_resource
    # ---------------------------
    def get_system_resource(self):
        """Get system resources data from Mikrotik"""
        self.data["resource"] = parse_api(
            data=self.data["resource"],
            source=self.api.path("/system/resource"),
            vals=[
                {"name": "platform", "default": "unknown"},
                {"name": "board-name", "default": "unknown"},
                {"name": "version", "default": "unknown"},
                {"name": "uptime", "default": "unknown"},
                {"name": "cpu-load", "default": "unknown"},
                {"name": "free-memory", "default": 0},
                {"name": "total-memory", "default": 0},
                {"name": "free-hdd-space", "default": 0},
                {"name": "total-hdd-space", "default": 0},
            ],
        )

        if self.data["resource"]["total-memory"] > 0:
            self.data["resource"]["memory-usage"] = round(
                (
                    (
                        self.data["resource"]["total-memory"]
                        - self.data["resource"]["free-memory"]
                    )
                    / self.data["resource"]["total-memory"]
                )
                * 100
            )
        else:
            self.data["resource"]["memory-usage"] = "unknown"

        if self.data["resource"]["total-hdd-space"] > 0:
            self.data["resource"]["hdd-usage"] = round(
                (
                    (
                        self.data["resource"]["total-hdd-space"]
                        - self.data["resource"]["free-hdd-space"]
                    )
                    / self.data["resource"]["total-hdd-space"]
                )
                * 100
            )
        else:
            self.data["resource"]["hdd-usage"] = "unknown"

    # ---------------------------
    #   get_firmware_update
    # ---------------------------
    def get_firmware_update(self):
        """Check for firmware update on Mikrotik"""
        self.data["fw-update"] = parse_api(
            data=self.data["fw-update"],
            source=self.api.path("/system/package/update"),
            vals=[
                {"name": "status"},
                {"name": "channel", "default": "unknown"},
                {"name": "installed-version", "default": "unknown"},
                {"name": "latest-version", "default": "unknown"},
            ],
        )

        if "status" in self.data["fw-update"]:
            self.data["fw-update"]["available"] = (
                True if self.data["fw-update"][
                            "status"] == "New version is available"
                else False
            )
        else:
            self.data["fw-update"]["available"] = False

    # ---------------------------
    #   get_script
    # ---------------------------
    def get_script(self):
        """Get list of all scripts from Mikrotik"""
        self.data["script"] = parse_api(
            data=self.data["script"],
            source=self.api.path("/system/script"),
            key="name",
            vals=[
                {"name": "name"},
                {"name": "last-started", "default": "unknown"},
                {"name": "run-count", "default": "unknown"},
            ],
        )

    # ---------------------------
    #   get_queue
    # ---------------------------

    def get_queue(self):
        """Get Queue data from Mikrotik"""
        self.data["queue"] = parse_api(
            data=self.data["queue"],
            source=self.api.path("/queue/simple"),
            key="name",
            vals=[
                {"name": ".id"},
                {"name": "name", "default": "unknown"},
                {"name": "target", "default": "unknown"},
                {"name": "max-limit", "default": "0/0"},
                {"name": "limit-at", "default": "0/0"},
                {"name": "burst-limit", "default": "0/0"},
                {"name": "burst-threshold", "default": "0/0"},
                {"name": "burst-time", "default": "0s/0s"},
                {"name": "packet-marks", "default": "none"},
                {"name": "parent", "default": "none"},
                {"name": "comment"},
                {
                    "name": "enabled",
                    "source": "disabled",
                    "type": "bool",
                    "reverse": True,
                },
            ]
        )

        traffic_type, traffic_div = self._get_traffic_type_and_div()

        for uid in self.data["queue"]:
            upload_max_limit_bps, download_max_limit_bps = [int(x) for x in
                                                            self.data["queue"][uid]["max-limit"].split('/')]
            self.data["queue"][uid]["upload-max-limit"] = \
                f"{round(upload_max_limit_bps * traffic_div)} {traffic_type}"
            self.data["queue"][uid]["download-max-limit"] = \
                f"{round(download_max_limit_bps * traffic_div)} {traffic_type}"

            upload_limit_at_bps, download_limit_at_bps = [int(x) for x in
                                                          self.data["queue"][uid]["limit-at"].split('/')]
            self.data["queue"][uid]["upload-limit-at"] = \
                f"{round(upload_limit_at_bps * traffic_div)} {traffic_type}"
            self.data["queue"][uid]["download-limit-at"] = \
                f"{round(download_limit_at_bps * traffic_div)} {traffic_type}"

            upload_burst_limit_bps, download_burst_limit_bps = [int(x) for x in
                                                                self.data["queue"][uid]["burst-limit"].split('/')]
            self.data["queue"][uid]["upload-burst-limit"] = \
                f"{round(upload_burst_limit_bps * traffic_div)} {traffic_type}"
            self.data["queue"][uid]["download-burst-limit"] = \
                f"{round(download_burst_limit_bps * traffic_div)} {traffic_type}"

            upload_burst_threshold_bps,\
                download_burst_threshold_bps = [int(x) for x in self.data["queue"][uid]["burst-threshold"].split('/')]

            self.data["queue"][uid]["upload-burst-threshold"] = \
                f"{round(upload_burst_threshold_bps * traffic_div)} {traffic_type}"
            self.data["queue"][uid]["download-burst-threshold"] = \
                f"{round(download_burst_threshold_bps * traffic_div)} {traffic_type}"

            upload_burst_time, download_burst_time = self.data["queue"][uid]["burst-time"].split('/')
            self.data["queue"][uid]["upload-burst-time"] = upload_burst_time
            self.data["queue"][uid]["download-burst-time"] = download_burst_time

    # ---------------------------
    #   get_dhcp
    # ---------------------------
    def get_dhcp(self):
        """Get DHCP data from Mikrotik"""

        self.data["dhcp-server"] = parse_api(
            data=self.data["dhcp-server"],
            source=self.api.path("/ip/dhcp-server"),
            key="name",
            vals=[
                {"name": "name"},
                {"name": "interface", "default": ""},
            ]
        )

        # Build list of local DHCP networks
        dhcp_networks = parse_api(
            data={},
            source=self.api.path("/ip/dhcp-server/network"),
            key="address",
            vals=[
                {"name": "address"},
            ],
            ensure_vals=[
                {"name": "address"},
            ]
        )
        self.local_dhcp_networks = [IPv4Network(network) for network in dhcp_networks]

        self.data["dhcp"] = parse_api(
            data=self.data["dhcp"],
            source=self.api.path("/ip/dhcp-server/lease"),
            key="mac-address",
            vals=[
                {"name": "mac-address"},
                {"name": "address", "default": "unknown"},
                {"name": "host-name", "default": "unknown"},
                {"name": "status", "default": "unknown"},
                {"name": "last-seen", "default": "unknown"},
                {"name": "server", "default": "unknown"},
                {"name": "comment"},
            ],
            ensure_vals=[
                {"name": "interface"},
                {"name": "available", "type": "bool", "default": False},
            ]
        )

        for uid in self.data["dhcp"]:
            self.data["dhcp"][uid]['interface'] = \
                self.data["dhcp-server"][self.data["dhcp"][uid]['server']]["interface"]

            self.data["dhcp"][uid]['available'] = \
                self.api.arp_ping(self.data["dhcp"][uid]['address'], self.data["dhcp"][uid]['interface'])

    def _address_part_of_local_network(self, address):
        address = ip_address(address)
        for network in self.local_dhcp_networks:
            if address in network:
                return True
        return False

    def _get_accounting_mac_by_ip(self, requested_ip):
        for mac, vals in self.data['accounting'].items():
            if vals.get('address') is requested_ip:
                return mac
        return None

    def get_accounting(self):
        """Get Accounting data from Mikrotik"""
        # Check if accounting and account-local-traffic is enabled
        accounting_enabled, local_traffic_enabled = self.api.is_accounting_and_local_traffic_enabled()
        traffic_type, traffic_div = self._get_traffic_type_and_div()

        if not accounting_enabled:
            # If any hosts were created return counters to 0 so sensors wont get stuck on last value
            for mac, vals in self.data["accounting"].items():
                self.data['accounting'][mac]["tx-rx-attr"] = traffic_type
                if 'wan-tx' in vals:
                    self.data["accounting"][mac]['wan-tx'] = 0.0
                if 'wan-rx' in vals:
                    self.data["accounting"][mac]['wan-rx'] = 0.0
                if 'lan-tx' in vals:
                    self.data["accounting"][mac]['lan-tx'] = 0.0
                if 'lan-rx' in vals:
                    self.data["accounting"][mac]['lan-rx'] = 0.0
            return

        # Build missing hosts from already retrieved DHCP Server leases
        for mac, vals in self.data["dhcp"].items():
            if mac not in self.data["accounting"]:
                self.data["accounting"][mac] = {
                    'address': vals['address'],
                    'mac-address': vals['mac-address'],
                    'host-name': vals['host-name'],
                    'comment': vals['comment']
                }

        # Build missing hosts from already retrieved ARP list
        host_update_from_arp = False
        for entry in self.raw_arp_entries:
            if entry['mac-address'] not in self.data["accounting"]:
                self.data["accounting"][entry['mac-address']] = {
                    'address': entry['address'],
                    'mac-address': entry['mac-address'],
                    'host-name': '',
                    'comment': ''
                }
                host_update_from_arp = True

        # If some host was added from ARP table build new host-name for it from static DNS entry. Fallback to MAC
        if host_update_from_arp:
            dns_data = parse_api(
                data={},
                source=self.api.path("/ip/dns/static"),
                key="address",
                vals=[
                    {"name": "address"},
                    {"name": "name"},
                ],
            )

            # Try to build hostname from DNS static entry
            for mac, vals in self.data["accounting"].items():
                if not str(vals.get('host-name', '')).strip() or vals['host-name'] is 'unknown':
                    if vals['address'] in dns_data and str(dns_data[vals['address']].get('name', '')).strip():
                        self.data["accounting"][mac]['host-name'] = dns_data[vals['address']]['name']

        # Check if any host still have empty 'host-name'. Default it to MAC.
        # Same check for 'comment' (pretty name)
        for mac, vals in self.data["accounting"].items():
            if not str(vals.get('host-name', '')).strip() or vals['host-name'] is 'unknown':
                self.data["accounting"][mac]['host-name'] = mac
            if not str(vals.get('comment', '')).strip() or vals['host-name'] is 'comment':
                self.data["accounting"][mac]['comment'] = mac

        _LOGGER.debug(f"Working with {len(self.data['accounting'])} accounting devices")

        # Build temp accounting values dict with ip address as key
        # Also set traffic type for each item
        tmp_accounting_values = {}
        for mac, vals in self.data['accounting'].items():
            tmp_accounting_values[vals['address']] = {
                "wan-tx": 0,
                "wan-rx": 0,
                "lan-tx": 0,
                "lan-rx": 0
            }
            self.data['accounting'][mac]["tx-rx-attr"] = traffic_type

        time_diff = self.api.take_accounting_snapshot()
        if time_diff:
            accounting_data = parse_api(
                data={},
                source=self.api.path("/ip/accounting/snapshot"),
                key=".id",
                vals=[
                    {"name": ".id"},
                    {"name": "src-address"},
                    {"name": "dst-address"},
                    {"name": "bytes", "default": 0},
                ],
            )

            for item in accounting_data.values():
                source_ip = str(item.get('src-address')).strip()
                destination_ip = str(item.get('dst-address')).strip()
                bits_count = int(str(item.get('bytes')).strip()) * 8

                if self._address_part_of_local_network(source_ip) and self._address_part_of_local_network(destination_ip):
                    # LAN TX/RX
                    if source_ip in tmp_accounting_values:
                        tmp_accounting_values[source_ip]['lan-tx'] += bits_count
                    if destination_ip in tmp_accounting_values:
                        tmp_accounting_values[destination_ip]['lan-rx'] += bits_count
                elif self._address_part_of_local_network(source_ip) and \
                        not self._address_part_of_local_network(destination_ip):
                    # WAN TX
                    if source_ip in tmp_accounting_values:
                        tmp_accounting_values[source_ip]['wan-tx'] += bits_count
                elif not self._address_part_of_local_network(source_ip) and \
                        self._address_part_of_local_network(destination_ip):
                    # WAN RX
                    if destination_ip in tmp_accounting_values:
                        tmp_accounting_values[destination_ip]['wan-rx'] += bits_count

            # Now that we have sum of all traffic in bytes for given period
            #   calculate real throughput and transform it to appropriate unit
            for addr in tmp_accounting_values:
                mac = self._get_accounting_mac_by_ip(addr)
                if not mac:
                    _LOGGER.debug(f"Address {addr} not found in accounting data, skipping update")
                    continue

                self.data['accounting'][mac]['wan-tx'] = round(
                    tmp_accounting_values[addr]['wan-tx'] / time_diff * traffic_div, 2)
                self.data['accounting'][mac]['wan-rx'] = round(
                    tmp_accounting_values[addr]['wan-rx'] / time_diff * traffic_div, 2)

                if local_traffic_enabled:
                    self.data['accounting'][mac]['lan-tx'] = round(
                        tmp_accounting_values[addr]['lan-tx'] / time_diff * traffic_div, 2)
                    self.data['accounting'][mac]['lan-rx'] = round(
                        tmp_accounting_values[addr]['lan-rx'] / time_diff * traffic_div, 2)
                else:
                    # If local traffic was enabled earlier and then disabled return counters for LAN traffic to 0
                    if 'lan-tx' in self.data['accounting'][mac]:
                        self.data['accounting'][mac]['lan-tx'] = 0.0
                    if 'lan-rx' in self.data['accounting'][mac]:
                        self.data['accounting'][mac]['lan-rx'] = 0.0
        else:
            # No time diff, just initialize/return counters to 0 for all
            for addr in tmp_accounting_values:
                mac = self._get_accounting_mac_by_ip(addr)
                if not mac:
                    _LOGGER.debug(f"Address {addr} not found in accounting data, skipping update")
                    continue

                self.data['accounting'][mac]['wan-tx'] = 0.0
                self.data['accounting'][mac]['wan-rx'] = 0.0

                if local_traffic_enabled:
                    self.data['accounting'][mac]['lan-tx'] = 0.0
                    self.data['accounting'][mac]['lan-rx'] = 0.0
