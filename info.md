{% if installed %}
{% if version_installed.replace("v", "").replace(".","") | int < 15  %}
**IMPORTANT: Integration needs to be re-added to take advantage of all new features.**
{% endif %}
{% endif %}

Monitor and control your Mikrotik device from Home Assistant.

![Mikrotik Logo](https://raw.githubusercontent.com/tomaae/homeassistant-mikrotik_router/master/docs/assets/images/ui/header.png)
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

## Links
- [Documentation](https://github.com/tomaae/homeassistant-mikrotik_router/tree/master)
- [Configuration](https://github.com/tomaae/homeassistant-mikrotik_router/tree/master#setup-integration)
- [Report a Bug](https://github.com/tomaae/homeassistant-mikrotik_router/issues/new?labels=bug&template=bug_report.md&title=%5BBug%5D)
- [Suggest an idea](https://github.com/tomaae/homeassistant-mikrotik_router/issues/new?labels=enhancement&template=feature_request.md&title=%5BFeature%5D)

[![ko-fi](https://www.ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/G2G71MKZG)
