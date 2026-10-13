"""Entity attributes that leave the data must not linger."""

from types import SimpleNamespace

from custom_components.mikrotik_router.entity import MikrotikEntity


def test_attributes_are_rebuilt_on_every_read() -> None:
    entity = object.__new__(MikrotikEntity)
    entity._attr_extra_state_attributes = {"attribution": "x"}
    entity.entity_description = SimpleNamespace(
        data_attributes_list=["sfp-temperature", "rate"]
    )
    entity._data = {"sfp-temperature": 40, "rate": "10Gbps"}

    first = entity.extra_state_attributes
    assert first == {"attribution": "x", "sfp_temperature": 40, "rate": "10Gbps"}

    # RouterOS stops reporting the temperature
    entity._data = {"rate": "10Gbps"}
    assert entity.extra_state_attributes == {"attribution": "x", "rate": "10Gbps"}
    assert entity._attr_extra_state_attributes == {"attribution": "x"}
