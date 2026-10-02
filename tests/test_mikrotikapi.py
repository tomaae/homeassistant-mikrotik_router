"""Regression tests for optional RouterOS queries."""

from unittest.mock import MagicMock

import pytest
from librouteros.exceptions import MultiTrapError, TrapError

from custom_components.mikrotik_router.mikrotikapi import MikrotikAPI


@pytest.mark.parametrize("stage", ["path", "list", "command"])
@pytest.mark.parametrize("multiple", [False, True])
@pytest.mark.parametrize("ignore_trap", [False, True])
def test_query_traps(stage, multiple, ignore_trap):
    """Optional traps leave the connection usable; required queries still fail."""
    error = TrapError("no such command or directory (wifi)")
    if multiple:
        error = MultiTrapError(error, TrapError("no such command prefix"))

    api = MikrotikAPI("router.example", "test", "test", use_ssl=False)
    connection = MagicMock()
    api._connection = connection
    api._connected = True
    response = connection.path.return_value
    if stage == "path":
        connection.path.side_effect = error
    elif stage == "list":
        response.__iter__.side_effect = error
    else:
        response.return_value.__iter__.side_effect = error

    assert (
        api.query(
            "/interface/wifi",
            command="print" if stage == "command" else None,
            ignore_trap=ignore_trap,
        )
        is None
    )
    assert api.connected() is ignore_trap

    # A subsequent supported query must work without another login.
    if ignore_trap:
        connection.path.side_effect = None
        connection.path.return_value = [{"name": "ether1"}]
        assert api.query("/interface") == [{"name": "ether1"}]
        assert api._connection is connection


@pytest.mark.parametrize("stage", ["path", "list", "command"])
def test_optional_query_transport_error_disconnects(stage):
    """Ignoring RouterOS traps must not hide a broken transport."""
    api = MikrotikAPI("router.example", "test", "test", use_ssl=False)
    connection = MagicMock()
    api._connection = connection
    api._connected = True
    error = ConnectionError("Connection closed")
    response = connection.path.return_value
    if stage == "path":
        connection.path.side_effect = error
    elif stage == "list":
        response.__iter__.side_effect = error
    else:
        response.return_value.__iter__.side_effect = error

    assert (
        api.query(
            "/interface/wifi",
            command="print" if stage == "command" else None,
            ignore_trap=True,
        )
        is None
    )
    assert not api.connected()
