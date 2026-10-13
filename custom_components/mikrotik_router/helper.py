"""Helper functions for Mikrotik Router."""

from __future__ import annotations

import ipaddress
import re

from homeassistant.util import slugify

from .const import DEFAULT_PORT, DOMAIN

INVALID_ROUTER_IDENTIFIERS = {"", "n/a", "none", "unknown"}


# ---------------------------
#   child_device_identifier
# ---------------------------
def child_device_identifier(
    entry_id: str, group: str, key: str | None = None
) -> tuple[str, str]:
    """Return the identifier of a child device of the router device."""
    suffix = slugify(group) if key is None else f"{slugify(group)}-{key}"
    return (DOMAIN, f"{entry_id}-{suffix}")


# ---------------------------
#   format_attribute
# ---------------------------
def format_attribute(attr):
    res = attr.replace("-", "_")
    res = res.replace(" ", "_")
    res = res.lower()
    return res


# ---------------------------
#   format_value
# ---------------------------
def format_value(res):
    res = res.replace("dhcp", "DHCP")
    res = res.replace("dns", "DNS")
    res = res.replace("capsman", "CAPsMAN")
    res = res.replace("wireless", "Wireless")
    res = res.replace("restored", "Restored")
    return res


# ---------------------------
#   normalize_routeros_version
# ---------------------------
def normalize_routeros_version(version: str) -> str:
    """Strip channel suffixes like '7.23 (stable)' for version comparisons."""
    match = re.search(r"(\d+\.\d+(?:\.\d+)?)", str(version))
    if not match:
        raise ValueError(f"Version format is not recognized: {version}")
    return match.group(1)


# ---------------------------
#   parse_routeros_major_minor
# ---------------------------
def parse_routeros_major_minor(version: str) -> tuple[int, int]:
    """Return major/minor integers from a RouterOS version string."""
    parts = normalize_routeros_version(version).split(".")
    return int(parts[0]), int(parts[1])


# ---------------------------
#   normalize_router_host
# ---------------------------
def normalize_router_host(host: str) -> str:
    """Normalize a router host for fallback identity matching."""
    normalized_host = host.strip().strip("[]")
    try:
        return ipaddress.ip_address(normalized_host).compressed
    except ValueError:
        return normalized_host.rstrip(".").casefold()


# ---------------------------
#   router_unique_id
# ---------------------------
def router_unique_id(
    host: str,
    port: int = DEFAULT_PORT,
    use_ssl: bool = False,
    serial_number=None,
    software_id=None,
    system_id=None,
) -> str:
    """Return the best available unique ID for a router."""
    for prefix, identifier in (
        ("routerboard", serial_number),
        ("routeros-system-id", system_id),
        ("routeros-software-id", software_id),
    ):
        if identifier is None:
            continue

        normalized_identifier = str(identifier).strip().casefold()
        if normalized_identifier not in INVALID_ROUTER_IDENTIFIERS:
            return f"{prefix}:{normalized_identifier}"

    effective_port = port or (8729 if use_ssl else 8728)
    return f"endpoint:{normalize_router_host(host)}|{effective_port}"
