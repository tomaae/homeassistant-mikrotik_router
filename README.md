# Mikrotik Router
![GitHub release (latest by date)](https://img.shields.io/github/v/release/tomaae/homeassistant-mikrotik_router?style=plastic)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=plastic)](https://github.com/custom-components/hacs)
[![License](https://img.shields.io/github/license/tomaae/homeassistant-mikrotik_router?style=plastic)](LICENSE.md)
![Project Stage](https://img.shields.io/badge/project%20stage-development-yellow.svg?style=plastic)

![GitHub commits since latest release](https://img.shields.io/github/commits-since/tomaae/homeassistant-mikrotik_router/latest?style=plastic)
![GitHub commit activity](https://img.shields.io/github/commit-activity/m/tomaae/homeassistant-mikrotik_router?style=plastic)


Monitor and control your Mikrotik device from Home Assistant.
![Tracker and sensors](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/device_tracker.png)

![Interface Info](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/interface.png)
![Interface Switch](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/interface_switch.png)
![Script Switch](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/script_switch.png)
![NAT switch](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/nat.png)


Features:
 * Interface device tracker
 * Enable/disable interface switches
 * Enable/disable NAT rule switches
 * System sensors (CPU, Memory, HDD)
 * Firmware update binary sensor
 * Switches to run scripts

# Setup integration
Setup this integration for your Mikrotik device in Home Assistant via `Configuration -> Integrations -> Add -> Mikrotik Router`.
You can add this integration several times for different devices.

![Add Integration](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/setup_integration.png)
* "Host" - Use hostname or IP
* "Port" - Leave at 0 for defaults
* "Name of the integration" - Friendy name for this router

# Configuration
![Integration options](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/integration_options.png)
* "Show client MAC and IP" - Display connected IP and MAC address for devices connected to ports on router.
* "Scan interval" - Scan/refresh time in seconds. HA needs to be reloaded for scan interval change to be applied.

## List of detected devices
![Integration options](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/integration_devices.png)
