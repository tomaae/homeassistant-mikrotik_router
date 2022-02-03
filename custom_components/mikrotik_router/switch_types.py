"""Definitions for Mikrotik Router sensor entities."""
from dataclasses import dataclass, field
from typing import List
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import EntityCategory
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntityDescription,
)

from .const import DOMAIN


DEVICE_ATTRIBUTES_CLIENT_TRAFFIC = ["address", "mac-address", "host-name"]


@dataclass
class MikrotikSwitchEntityDescription(SwitchEntityDescription):
    """Class describing mikrotik entities."""

    device_class: str = SwitchDeviceClass.SWITCH

    ha_group: str = ""
    ha_connection: str = ""
    ha_connection_value: str = ""
    data_path: str = ""
    data_attribute: str = ""
    data_name: str = ""
    data_uid: str = ""
    data_reference: str = ""
    data_attributes_list: List = field(default_factory=lambda: [])


SENSOR_TYPES = {
    "system_temperature": MikrotikSwitchEntityDescription(
        key="system_temperature",
        name="Temperature",
        icon="mdi:thermometer",
        entity_category=None,
        ha_group="System",
        data_path="health",
        data_attribute="temperature",
        data_name="",
        data_uid="",
        data_reference="",
    ),
}
