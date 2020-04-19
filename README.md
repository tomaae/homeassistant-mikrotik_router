# Mikrotik Router
![GitHub release (latest by date)](https://img.shields.io/github/v/release/tomaae/homeassistant-mikrotik_router?style=plastic)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=plastic)](https://github.com/custom-components/hacs)
![Project Stage](https://img.shields.io/badge/project%20stage-development-yellow.svg?style=plastic)

![GitHub commits since latest release](https://img.shields.io/github/commits-since/tomaae/homeassistant-mikrotik_router/latest?style=plastic)
![GitHub commit activity](https://img.shields.io/github/commit-activity/m/tomaae/homeassistant-mikrotik_router?style=plastic)

[![ko-fi](https://www.ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/G2G71MKZG)

![Mikrotik Logo](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/header.png)

Monitor and control your Mikrotik device from Home Assistant.

 * Interfaces:
   * Enable/disable interfaces
   * Monitor RX/TX traffic per interface
   * Monitor device presence per interface
   * IP, MAC, Link information per interface for connected devices
 * Enable/disable NAT rule switches
 * Enable/disable Simple Queue switches
 * Mikrotik Accounting traffic sensors per hosts for RX/TX WAN/LAN
 * Device tracker for hosts in network
 * System sensors (CPU, Memory, HDD)
 * Check firmware update
 * Execute scripts
 * Configurable update interval
 * Configurable traffic unit (bps, Kbps, Mbps, B/s, KB/s, MB/s)
 * Supports monitoring of multiple mikrotik devices simultaneously

## Features
## Interfaces
Monitor and control status on each Mikrotik interface, both lan and wlan. Both physical and virtual.

![Interface Info](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/interface.png)
![Interface Switch](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/interface_switch.png)
![Interface Sensor](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/interface_sensor.png)

## NAT
Monitor and control individual NAT rules.

More information about NAT rules can be found on [Mikrotik support page](https://wiki.mikrotik.com/wiki/Manual:IP/Firewall/NAT).

NOTE: dst-port and protocol combination must be unique for each rule. All conflicting NAT rules will not be available in HA.

![NAT switch](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/nat.png)

## Simple Queue
Control simple queues.

More information about simple queues can be found on [Mikrotik support page](https://wiki.mikrotik.com/wiki/Manual:Queue#Simple_Queues).

![Queue switch](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/queue_switch.png)

## Host Tracking
Track availability of all network devices. All devices visible to Mikrotik device can be tracked, including: LAN connected devices and both Wireless and CAPsMAN from Mikrotik wireless package.

NOTE: Host Tracking is disabled by default and has to be enabled in integration options.

![Host tracker](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/host_tracker.png)

## Scripts
Execute Mikrotik Router scripts.

![Script Switch](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/script_switch.png)

## Accounting
Monitor per-IP throughput tracking based on Mikrotik Accounting.

Feature is present in Winbox IP-Accounting. Make sure that threshold is set to reasonable value to store all connections between user defined scan interval. Max value is 8192 so for piece of mind I recommend setting that value.

More information about Accounting can be found on [Mikrotik support page](https://wiki.mikrotik.com/wiki/Manual:IP/Accounting).

![Accounting sensor](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/accounting_sensor.png)

# Install integration
This integration is distributed using [HACS](https://hacs.xyz/).

You can find it under "Integrations", named "Mikrotik Router"

## Setup integration
1. Create user for homeassistant on your mikrotik router with following permissions:
   * read, write, api, test
2. If you want to be able to execute scripts on your mikrotik router from HA, script needs to have only following policies:
   * read, write, test
or check "Don't Require Permissions" option
3. Setup this integration for your Mikrotik device in Home Assistant via `Configuration -> Integrations -> Add -> Mikrotik Router`.
You can add this integration several times for different devices.

NOTE: Do not mistake "Mikrotik Router" integration with HA build-in integration named "Mikrotik".

![Add Integration](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/setup_integration.png)
* "Name of the integration" - Friendly name for this router
* "Host" - Use hostname or IP
* "Port" - Leave at 0 for defaults

## Configuration
![Integration options](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/integration_options.png)
* "Scan interval" - Scan/refresh time in seconds. HA needs to be reloaded for scan interval change to be applied
* "Unit of measurement" - Traffic sensor measurement (bps, Kbps, Mbps, B/s, KB/s, MB/s)
* "Show client MAC and IP on interfaces" - Display connected IP and MAC address for devices connected to ports on router
* "Track network devices" - Enable device tracker
* "Track network devices timeout" - Tracked devices will be marked as away after timeout (does not apply to Mikrotik wireless and caps-man)

# Development

## Translation
To help out with the translation you need an account on Lokalise, the easiest way to get one is to [click here](https://lokalise.com/login/) then select "Log in with GitHub".
After you have created your account [click here to join Mikrotik Router project on Lokalise](https://app.lokalise.com/public/581188395e9778a6060128.17699416/).

If you want to add translations for a language that is not listed please [open a Feature request](https://github.com/tomaae/homeassistant-mikrotik_router/issues/new?labels=enhancement&title=%5BLokalise%5D%20Add%20new%20translations%20language).

## Enabling debug
To enable debug for Mikrotik router integration, add following to your configuration.yaml:
```
logger:
  default: info
  logs:
    custom_components.mikrotik_router: debug
```
