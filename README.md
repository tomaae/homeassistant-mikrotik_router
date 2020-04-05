# Mikrotik Router
![GitHub release (latest by date)](https://img.shields.io/github/v/release/tomaae/homeassistant-mikrotik_router?style=plastic)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=plastic)](https://github.com/custom-components/hacs)
![Project Stage](https://img.shields.io/badge/project%20stage-development-yellow.svg?style=plastic)

![GitHub commits since latest release](https://img.shields.io/github/commits-since/tomaae/homeassistant-mikrotik_router/latest?style=plastic)
![GitHub commit activity](https://img.shields.io/github/commit-activity/m/tomaae/homeassistant-mikrotik_router?style=plastic)

![Tracker and sensors](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/header.png)

Monitor and control your Mikrotik device from Home Assistant.

Features:
 * Interfaces:
   * Enable/disable interfaces
   * Monitor RX/TX traffic per interface
   * Monitor device presence per interface
   * IP, MAC, Link information per interface for connected devices
 * Enable/disable NAT rule switches
 * Enable/disable Simple Queue switches
 * System sensors (CPU, Memory, HDD)
 * Check firmware update
 * Execute scripts
 * Configurable update interval
 * Configurable traffic unit (bps, Kbps, Mbps, B/s, KB/s, MB/s)
 * Supports monitoring of multiple mikrotik devices simultaneously

# Integration preview
![Tracker and sensors](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/device_tracker.png)

![Interface Info](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/interface.png)
![Interface Switch](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/interface_switch.png)

![Interface Sensor](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/interface_sensor.png)
![Script Switch](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/script_switch.png)

![NAT switch](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/nat.png)
![Queue switch](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/queue_switch.png)

# Setup integration
Setup this integration for your Mikrotik device in Home Assistant via `Configuration -> Integrations -> Add -> Mikrotik Router`.
You can add this integration several times for different devices.

![Add Integration](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/setup_integration.png)
* "Host" - Use hostname or IP
* "Port" - Leave at 0 for defaults
* "Name of the integration" - Friendy name for this router
* "Unit of measurement" - Traffic sensor measurement (bps, Kbps, Mbps, B/s, KB/s, MB/s)

# Configuration
![Integration options](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/integration_options.png)
* "Show client MAC and IP" - Display connected IP and MAC address for devices connected to ports on router.
* "Scan interval" - Scan/refresh time in seconds. HA needs to be reloaded for scan interval change to be applied.
* "Unit of measurement" - Traffic sensor measurement (bps, Kbps, Mbps, B/s, KB/s, MB/s)

## List of detected devices
![Integration options](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/integration_devices.png)
