## Mikrotik Router
![GitHub release (latest by date)](https://img.shields.io/github/v/release/tomaae/homeassistant-mikrotik_router?style=plastic)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=plastic)](https://github.com/custom-components/hacs)
[![License](https://img.shields.io/github/license/tomaae/homeassistant-mikrotik_router?style=plastic)](LICENSE.md)
![Project Stage](https://img.shields.io/badge/project%20stage-development-yellow.svg?style=plastic)

![GitHub commits since latest release](https://img.shields.io/github/commits-since/tomaae/homeassistant-mikrotik_router/latest?style=plastic)
![GitHub commit activity](https://img.shields.io/github/commit-activity/m/tomaae/homeassistant-mikrotik_router?style=plastic)

![aarch64-shield](https://img.shields.io/badge/aarch64-yes-green.svg?style=plastic)
![amd64-shield](https://img.shields.io/badge/amd64-yes-green.svg?style=plastic)
![armhf-shield](https://img.shields.io/badge/armhf-yes-green.svg?style=plastic)
![armv7-shield](https://img.shields.io/badge/armv7-yes-green.svg?style=plastic)

Monitor and control your Mikrotik Device from Home Assistant.
![Device Tracker](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/device_tracker.png)

Interface tracker:

![Interface Info](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/interface.png)

Features:
 * Interface device tracker
 * Enable/disable interface switches

## Add integration
You can add this integration to Home Assistant via `Configuration -> Integrations -> Add -> Mikrotik Router`. You can add this integration several times for different routers.

![Add Integration](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/setup_integration.png)
* "Host" - Use hostname or IP
* "Port" - Leave at 0 for defaults
* "Name of the integration" - Friendy name for this router

## Configuration
![Integration options](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/integration_options.png)
* "Show client MAC and IP" - Display connected IP and MAC address for devices connected to ports on router.
* "Scan interval" - Scan/refresh time in seconds. HA needs to be reloaded for scan interval change to be applied.

## List of detected devices
![Integration options](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/integration_devices.png)
