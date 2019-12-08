"""Mikrotik API for Mikrotik Router."""

import ssl
import logging
import os
import sys
import importlib
from .exceptions import OldLibrouteros, ApiEntryNotFound

MODULE_PATH = os.path.join(os.path.dirname(__file__), "librouteros", "__init__.py")
MODULE_NAME = "librouteros"
spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
librouteros = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = librouteros
spec.loader.exec_module(librouteros)

_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   MikrotikAPI
# ---------------------------
class MikrotikAPI:
    """Handle all communication with the Mikrotik API."""

    def __init__(self, host, username, password, port=0, use_ssl=True, login_method="plain", encoding="utf-8"):
        """Initialize the Mikrotik Client."""
        self._host = host
        self._use_ssl = use_ssl
        self._port = port
        self._username = username
        self._password = password
        self._login_method = login_method
        self._encoding = encoding
        self._ssl_wrapper = None

        self._connection = None
        self._connected = False
        self.error = ""

        self.check_library()

        # Default ports
        if not self._port:
            self._port = 8729 if self._use_ssl else 8728

    # ---------------------------
    #   check_library
    # ---------------------------
    def check_library(self):
        if not hasattr(librouteros.exceptions, 'ConnectionClosed'):
            error = "Invalid librouteros library version installed, possible conflict with other software."
            raise OldLibrouteros(error)

        if not hasattr(librouteros.exceptions, 'ProtocolError'):
            error = "Invalid librouteros library version installed, possible conflict with other software."
            raise OldLibrouteros(error)

    # ---------------------------
    #   connect
    # ---------------------------
    def connect(self):
        """Connect to Mikrotik device."""
        self.error = ""
        self._connected = None

        kwargs = {
            "encoding": self._encoding,
            "login_methods": self._login_method,
            "port": self._port,
        }

        if self._use_ssl:
            if self._ssl_wrapper is None:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                self._ssl_wrapper = ssl_context.wrap_socket
            kwargs["ssl_wrapper"] = self._ssl_wrapper

        try:
            self._connection = librouteros.connect(self._host, self._username, self._password, **kwargs)
        except (
                librouteros.exceptions.TrapError,
                librouteros.exceptions.MultiTrapError,
                librouteros.exceptions.ConnectionClosed,
                librouteros.exceptions.ProtocolError,
                librouteros.exceptions.FatalError
        ) as api_error:
            _LOGGER.error("Mikrotik %s: %s", self._host, api_error)
            self.error_to_strings("%s" % api_error)
            self._connection = None
            return False
        else:
            _LOGGER.info("Mikrotik Connected to %s", self._host)
            self._connected = True

        return self._connected

    # ---------------------------
    #   error_to_strings
    # ---------------------------
    def error_to_strings(self, error):
        """Translate error output to error string."""
        self.error = "cannot_connect"
        if error == "invalid user name or password (6)":
            self.error = "wrong_login"

        return

    # ---------------------------
    #   connected
    # ---------------------------
    def connected(self):
        """Return connected boolean."""
        return self._connected

    # ---------------------------
    #   path
    # ---------------------------
    def path(self, path):
        """Retrieve data from Mikrotik API."""
        if not self._connected or not self._connection:
            if not self.connect():
                return None

        try:
            response = self._connection.path(path)
            tuple(response)
        except librouteros.exceptions.ConnectionClosed:
            _LOGGER.error("Mikrotik %s connection closed", self._host)
            self._connected = False
            self._connection = None
            return None
        except (
                librouteros.exceptions.TrapError,
                librouteros.exceptions.MultiTrapError,
                librouteros.exceptions.ProtocolError,
                librouteros.exceptions.FatalError
        ) as api_error:
            _LOGGER.error("Mikrotik %s connection error %s", self._host, api_error)
            return None

        return response if response else None

    # ---------------------------
    #   update
    # ---------------------------
    def update(self, path, param, value, mod_param, mod_value):
        """Modify a parameter"""
        entry_found = False
        if not self._connected or not self._connection:
            if not self.connect():
                return None

        response = self.path(path)
        if response is None:
            return False

        for tmp in response:
            if param not in tmp:
                continue

            if tmp[param] != value:
                continue

            entry_found = True
            params = {
                '.id': tmp['.id'],
                mod_param: mod_value
            }

            try:
                response.update(**params)
            except librouteros.exceptions.ConnectionClosed:
                _LOGGER.error("Mikrotik %s connection closed", self._host)
                self._connected = False
                self._connection = None
                return None
            except (
                    librouteros.exceptions.TrapError,
                    librouteros.exceptions.MultiTrapError,
                    librouteros.exceptions.ProtocolError,
                    librouteros.exceptions.FatalError
            ) as api_error:
                _LOGGER.error("Mikrotik %s connection error %s", self._host, api_error)
                return None

        if not entry_found:
            error = "Parameter \"{}\" with value \"{}\" not found".format(param, value)
            raise ApiEntryNotFound(error)

        return True

    # ---------------------------
    #   run_script
    # ---------------------------
    def run_script(self, name):
        """Run script"""
        entry_found = False
        if not self._connected or not self._connection:
            if not self.connect():
                return None

        response = self.path('/system/script')
        if response is None:
            return False

        for tmp in response:
            if 'name' not in tmp:
                continue

            if tmp['name'] != name:
                continue

            entry_found = True
            try:
                run = response('run', **{'.id': tmp['.id']})
            except librouteros.exceptions.ConnectionClosed:
                _LOGGER.error("Mikrotik %s connection closed", self._host)
                self._connected = False
                self._connection = None
                return None
            except (
                    librouteros.exceptions.TrapError,
                    librouteros.exceptions.MultiTrapError,
                    librouteros.exceptions.ProtocolError,
                    librouteros.exceptions.FatalError
            ) as api_error:
                _LOGGER.error("Mikrotik %s connection error %s", self._host, api_error)
                return None

            tuple(run)

        if not entry_found:
            error = "Script \"{}\" not found".format(name)
            raise ApiEntryNotFound(error)

        return True
