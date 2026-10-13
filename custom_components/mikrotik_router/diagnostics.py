"""Diagnostics support for Mikrotik Router."""

from __future__ import annotations

import re
from collections.abc import Mapping
from ipaddress import ip_network
from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import TO_REDACT
from .coordinator import MikrotikConfigEntry

ENTRY_TO_REDACT = TO_REDACT | {CONF_HOST}
MAC_ADDRESS_PATTERN = re.compile(r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}")
IPV4_ADDRESS_PATTERN = re.compile(
    r"(?<![\d.])"
    r"(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1?\d?\d)"
    r"(?:/(?:3[0-2]|[12]?\d))?"
    r"(?![\d.])"
)
MAC_ADDRESS_FIELDS = {
    "mac-address",
    "active-mac-address",
    "orig-mac-address",
    "port-mac-address",
    "client-mac-address",
}
UNIQUE_ID_SENSITIVE_FIELDS = MAC_ADDRESS_FIELDS | {
    "ip-address",
    "client-ip-address",
    "address",
    "active-address",
    "client-id",
    "active-client-id",
    "gateway",
    "from-addresses",
    "to-addresses",
    "src-address",
    "dst-address",
    "caller-id",
    "target",
}
RUNTIME_TO_REDACT = TO_REDACT - MAC_ADDRESS_FIELDS


def _fake_mac_address(value: Any, mac_addresses: dict[str, str]) -> Any:
    """Replace a MAC address with a consistent locally administered address."""
    if not isinstance(value, str) or not MAC_ADDRESS_PATTERN.fullmatch(value):
        return value

    normalized_mac = value.replace("-", ":").upper()
    if normalized_mac not in mac_addresses:
        mac_index = len(mac_addresses) + 1
        fake_mac = "02:" + ":".join(
            f"{(mac_index >> shift) & 0xFF:02X}" for shift in (32, 24, 16, 8, 0)
        )
        mac_addresses[normalized_mac] = fake_mac
    return mac_addresses[normalized_mac]


def _redacted_identifier(value: str, redacted_keys: dict[str, str]) -> str:
    """Replace an identifier with a consistent redacted placeholder."""
    if value not in redacted_keys:
        redacted_keys[value] = f"{REDACTED}_{len(redacted_keys) + 1}"
    return redacted_keys[value]


def _redact_unique_id(
    value: Any,
    record: Mapping,
    mac_addresses: dict[str, str],
    redacted_keys: dict[str, str],
) -> Any:
    """Redact addresses embedded in a composite unique ID."""
    if not isinstance(value, str):
        return value

    redacted_value = MAC_ADDRESS_PATTERN.sub(
        lambda match: _fake_mac_address(match.group(0), mac_addresses),
        value,
    )
    sensitive_values = {
        field_value
        for field in UNIQUE_ID_SENSITIVE_FIELDS
        if isinstance((field_value := record.get(field)), str)
        and field_value
        and not MAC_ADDRESS_PATTERN.fullmatch(field_value)
        and field_value.casefold() not in {"any", "unknown", "none", "n/a"}
    }
    for sensitive_value in sorted(sensitive_values, key=len, reverse=True):
        replacement = _redacted_identifier(sensitive_value, redacted_keys)
        redacted_value = redacted_value.replace(sensitive_value, replacement)

    return IPV4_ADDRESS_PATTERN.sub(
        lambda match: _redacted_identifier(match.group(0), redacted_keys),
        redacted_value,
    )


def _redact_netwatch(
    data: Any,
    mac_addresses: dict[str, str],
    redacted_keys: dict[str, str],
) -> Any:
    """Redact Netwatch hosts used as record keys and values."""
    if not isinstance(data, Mapping):
        return _redact_sensitive_identifiers(data, mac_addresses, redacted_keys)

    redacted = {}
    for host, record in data.items():
        redacted_host = host
        if isinstance(host, str) and host:
            redacted_host = _redacted_identifier(host, redacted_keys)

        redacted_record = _redact_sensitive_identifiers(
            record, mac_addresses, redacted_keys
        )
        if isinstance(redacted_record, dict) and isinstance(record, Mapping):
            host_value = record.get("host")
            if isinstance(host_value, str) and host_value:
                redacted_record["host"] = _redacted_identifier(
                    host_value, redacted_keys
                )
        redacted[redacted_host] = redacted_record
    return redacted


def _is_sensitive_mapping_key(key: Any) -> bool:
    """Return whether a mapping key contains an IP or MAC address."""
    if not isinstance(key, str):
        return False
    if MAC_ADDRESS_PATTERN.fullmatch(key):
        return True
    if not any(separator in key for separator in (".", ":", "/")):
        return False
    try:
        ip_network(key, strict=False)
    except ValueError:
        return False
    return True


def _redact_sensitive_identifiers(
    data: Any,
    mac_addresses: dict[str, str],
    redacted_keys: dict[str, str],
) -> Any:
    """Replace sensitive identifiers while preserving their relationships."""
    if isinstance(data, str):
        return _fake_mac_address(data, mac_addresses)
    if isinstance(data, list):
        return [
            _redact_sensitive_identifiers(value, mac_addresses, redacted_keys)
            for value in data
        ]
    if not isinstance(data, Mapping):
        return data

    redacted = {}
    for key, value in data.items():
        redacted_key = key
        if isinstance(key, str) and MAC_ADDRESS_PATTERN.fullmatch(key):
            redacted_key = _fake_mac_address(key, mac_addresses)
        elif _is_sensitive_mapping_key(key):
            if key not in redacted_keys:
                redacted_keys[key] = f"{REDACTED}_{len(redacted_keys) + 1}"
            redacted_key = redacted_keys[key]
        if key == "netwatch":
            redacted[redacted_key] = _redact_netwatch(
                value, mac_addresses, redacted_keys
            )
        elif key == "uniq-id":
            redacted[redacted_key] = _redact_unique_id(
                value, data, mac_addresses, redacted_keys
            )
        else:
            redacted[redacted_key] = _redact_sensitive_identifiers(
                value, mac_addresses, redacted_keys
            )
    return redacted


def _redact_environment(data: Any) -> Any:
    """Redact the values of script environment variables.

    Scripts often keep tokens and passwords in global variables, and the value
    is stored under a generic key that is not redacted anywhere else.
    """
    if not isinstance(data, Mapping) or not isinstance(
        environment := data.get("environment"), Mapping
    ):
        return data

    return {
        **data,
        "environment": {
            name: (
                {**record, "value": REDACTED} if isinstance(record, Mapping) else record
            )
            for name, record in environment.items()
        },
    }


def _redact_runtime_data(
    data: Any,
    mac_addresses: dict[str, str],
    redacted_keys: dict[str, str],
) -> Any:
    """Redact sensitive runtime values and mapping keys."""
    return async_redact_data(
        _redact_sensitive_identifiers(
            _redact_environment(data), mac_addresses, redacted_keys
        ),
        RUNTIME_TO_REDACT,
    )


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: MikrotikConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data_coordinator = config_entry.runtime_data.data_coordinator
    tracker_coordinator = config_entry.runtime_data.tracker_coordinator
    mac_addresses = {}
    redacted_keys = {}

    return {
        "entry": {
            "data": async_redact_data(config_entry.data, ENTRY_TO_REDACT),
            "options": async_redact_data(config_entry.options, ENTRY_TO_REDACT),
        },
        "data": _redact_runtime_data(
            data_coordinator.data, mac_addresses, redacted_keys
        ),
        "tracker": _redact_runtime_data(
            tracker_coordinator.data, mac_addresses, redacted_keys
        ),
    }
