"""Script environment values must not reach diagnostics or debug logs."""

import logging

from homeassistant.components.diagnostics import REDACTED

from custom_components.mikrotik_router.apiparser import parse_api
from custom_components.mikrotik_router.diagnostics import _redact_runtime_data


def test_diagnostics_redact_environment_values() -> None:
    data = {
        "environment": {
            "ddns-token": {"name": "ddns-token", "value": "s3cret"},
            "other": {"name": "other", "value": "also-secret"},
        },
        "resource": {"version": "7.20"},
    }

    result = _redact_runtime_data(data, {}, {})

    assert result["environment"]["ddns-token"] == {
        "name": "ddns-token",
        "value": REDACTED,
    }
    assert result["environment"]["other"]["value"] == REDACTED
    assert result["resource"] == {"version": "7.20"}
    # The input is left untouched
    assert data["environment"]["ddns-token"]["value"] == "s3cret"


def test_parse_api_redacts_in_debug_log(caplog) -> None:
    source = [{"name": "ddns-token", "value": "s3cret"}]
    with caplog.at_level(
        logging.DEBUG, logger="custom_components.mikrotik_router.apiparser"
    ):
        data = parse_api(
            data={},
            source=source,
            key="name",
            redact={"value"},
            vals=[{"name": "name"}, {"name": "value"}],
        )

    assert data["ddns-token"]["value"] == "s3cret"
    assert "s3cret" not in caplog.text
    assert "Processing entry" in caplog.text
