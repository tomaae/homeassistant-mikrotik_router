"""SFP detection and the SFP temperature default."""

from custom_components.mikrotik_router.apiparser import parse_api
from custom_components.mikrotik_router.helper import is_sfp_port


def test_is_sfp_port() -> None:
    """Only a port with a reported shutdown temperature is an SFP port."""
    assert is_sfp_port({"sfp-shutdown-temperature": 95})
    assert not is_sfp_port({"sfp-shutdown-temperature": None})
    assert not is_sfp_port({"sfp-shutdown-temperature": ""})
    assert not is_sfp_port({})


def test_missing_sfp_temperature_is_none() -> None:
    """A copper port or an empty cage has no temperature, not 0 degrees."""
    data = parse_api(
        data={},
        source=[
            {"default-name": "ether1"},
            {"default-name": "sfp1", "sfp-shutdown-temperature": 95},
        ],
        key="default-name",
        vals=[
            {"name": "default-name"},
            {"name": "sfp-shutdown-temperature", "default": None},
        ],
    )
    assert data["ether1"]["sfp-shutdown-temperature"] is None
    assert data["sfp1"]["sfp-shutdown-temperature"] == 95

    data = parse_api(
        data={"sfp1": {"name": "sfp1"}},
        source=[{"name": "sfp1", "status": "no-link"}],
        key_search="name",
        vals=[{"name": "sfp-temperature", "default": None}],
    )
    assert data["sfp1"]["sfp-temperature"] is None
