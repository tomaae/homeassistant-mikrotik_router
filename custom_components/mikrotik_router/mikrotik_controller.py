"""Mikrotik Controller for Mikrotik Router."""

from datetime import timedelta
import asyncio
import logging
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

from .mikrotikapi import MikrotikAPI
from .helper import from_entry, parse_api
from .exceptions import ApiEntryNotFound

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
        }

        self.listeners = []
        self.lock = asyncio.Lock()

        self.api = MikrotikAPI(host, username, password, port, use_ssl)

        async_track_time_interval(
            self.hass, self.force_update, self.option_scan_interval
        )
        async_track_time_interval(
            self.hass, self.force_fwupdate_check, timedelta(hours=1)
        )

    # ---------------------------
    #   force_update
    # ---------------------------
    async def force_update(self, _now=None):
        """Trigger update by timer"""
        await self.async_update()

    # ---------------------------
    #   force_fwupdate_check
    # ---------------------------
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


        for uid in self.data["interface"]:
            self.data["interface"][uid]["rx-bits-per-second-attr"] = traffic_type
            self.data["interface"][uid]["tx-bits-per-second-attr"] = traffic_type
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
                from_entry(entry, "mac-address")
                if "mac-address" not in self.data["arp"][uid]
                else "multiple"
            )
            self.data["arp"][uid]["address"] = (
                from_entry(entry, "address")
                if "address" not in self.data["arp"][uid]
                else "multiple"
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
                self.data["arp"][uid]["mac-address"] = from_entry(entry, "mac-address")
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
    #   get_system_routerboard
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
                True
                if self.data["fw-update"]["status"] == "New version is available"
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
