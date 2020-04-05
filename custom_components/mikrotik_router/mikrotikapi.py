"""Mikrotik API for Mikrotik Router."""

import importlib
import logging
import os
import ssl
import sys
import time
from threading import Lock

from voluptuous import Optional

from .const import (
    DEFAULT_LOGIN_METHOD,
    DEFAULT_ENCODING,
)
from .exceptions import ApiEntryNotFound

MODULE_PATH = os.path.join(os.path.dirname(__file__), "librouteros_custom",
                           "__init__.py")
MODULE_NAME = "librouteros_custom"
spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
librouteros_custom = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = librouteros_custom
spec.loader.exec_module(librouteros_custom)

_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   MikrotikAPI
# ---------------------------
class MikrotikAPI:
    """Handle all communication with the Mikrotik API."""

    def __init__(
        self,
        host,
        username,
        password,
        port=0,
        use_ssl=True,
        login_method=DEFAULT_LOGIN_METHOD,
        encoding=DEFAULT_ENCODING,
    ):
        """Initialize the Mikrotik Client."""
        self._host = host
        self._use_ssl = use_ssl
        self._port = port
        self._username = username
        self._password = password
        self._login_method = login_method
        self._encoding = encoding
        self._ssl_wrapper = None
        self.lock = Lock()

        self._connection = None
        self._connected = False
        self._connection_epoch = 0
        self._connection_retry_sec = 58
        self.error = None
        self.connection_error_reported = False
        self.accounting_last_run = None

        # Default ports
        if not self._port:
            self._port = 8729 if self._use_ssl else 8728

    # ---------------------------
    #   disconnect
    # ---------------------------
    def disconnect(self):
        """Disconnect from Mikrotik device."""
        self._connected = False
        self._connection = None
        self._connection_epoch = 0

    # ---------------------------
    #   connect
    # ---------------------------
    def connect(self) -> bool:
        """Connect to Mikrotik device."""
        self.error = ""
        self._connected = None
        self._connection_epoch = time.time()

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
        self.lock.acquire()
        try:
            self._connection = librouteros_custom.connect(
                self._host, self._username, self._password, **kwargs
            )
        except (
            librouteros_custom.exceptions.TrapError,
            librouteros_custom.exceptions.MultiTrapError,
            librouteros_custom.exceptions.ConnectionClosed,
            librouteros_custom.exceptions.ProtocolError,
            librouteros_custom.exceptions.FatalError,
            ssl.SSLError,
            BrokenPipeError,
            OSError,
        ) as api_error:
            if not self.connection_error_reported:
                _LOGGER.error(
                    "Mikrotik %s error while connecting: %s", self._host,
                    api_error
                )
                self.connection_error_reported = True

            self.error_to_strings("%s" % api_error)
            self._connection = None
            self.lock.release()
            return False
        except:
            if not self.connection_error_reported:
                _LOGGER.error(
                    "Mikrotik %s error while connecting: %s", self._host,
                    "Unknown"
                )
                self.connection_error_reported = True

            self._connection = None
            self.lock.release()
            return False
        else:
            if self.connection_error_reported:
                _LOGGER.warning("Mikrotik Reconnected to %s", self._host)
                self.connection_error_reported = False
            else:
                _LOGGER.debug("Mikrotik Connected to %s", self._host)

            self._connected = True
            self.lock.release()

        return self._connected

    # ---------------------------
    #   error_to_strings
    # ---------------------------
    def error_to_strings(self, error):
        """Translate error output to error string."""
        self.error = "cannot_connect"
        if error == "invalid user name or password (6)":
            self.error = "wrong_login"

        if "ALERT_HANDSHAKE_FAILURE" in error:
            self.error = "ssl_handshake_failure"

    # ---------------------------
    #   connected
    # ---------------------------
    def connected(self) -> bool:
        """Return connected boolean."""
        return self._connected

    # ---------------------------
    #   path
    # ---------------------------
    def path(self, path, return_list=False) -> Optional(list):
        """Retrieve data from Mikrotik API."""
        """Returns generator object, unless return_list passed as True"""
        if not self._connected or not self._connection:
            if self._connection_epoch > time.time() - self._connection_retry_sec:
                return None

            if not self.connect():
                return None

        self.lock.acquire()
        try:
            response = self._connection.path(path)
            _LOGGER.debug("API response (%s): %s", path, response)
        except librouteros_custom.exceptions.ConnectionClosed:
            if not self.connection_error_reported:
                _LOGGER.error("Mikrotik %s connection closed", self._host)
                self.connection_error_reported = True

            self.disconnect()
            self.lock.release()
            return None
        except (
                librouteros_custom.exceptions.TrapError,
                librouteros_custom.exceptions.MultiTrapError,
                librouteros_custom.exceptions.ProtocolError,
                librouteros_custom.exceptions.FatalError,
                ssl.SSLError,
                BrokenPipeError,
                OSError,
                ValueError,
        ) as api_error:
            if not self.connection_error_reported:
                _LOGGER.error("Mikrotik %s error while path %s", self._host, api_error)
                self.connection_error_reported = True

            self.disconnect()
            self.lock.release()
            return None
        except:
            if not self.connection_error_reported:
                _LOGGER.error("Mikrotik %s error while path %s", self._host, "unknown")
                self.connection_error_reported = True

            self.disconnect()
            self.lock.release()
            return None

        if return_list:
            try:
                response = list(response)
            except librouteros_custom.exceptions.ConnectionClosed as api_error:
                if not self.connection_error_reported:
                    _LOGGER.error("Mikrotik %s error while building list for path %s", self._host, api_error)
                    self.connection_error_reported = True

                self.disconnect()
                self.lock.release()
                return None
            except:
                if not self.connection_error_reported:
                    _LOGGER.error("Mikrotik %s error while building list for path %s", self._host, "unknown")
                    self.connection_error_reported = True

                self.disconnect()
                self.lock.release()
                return None

        self.lock.release()
        return response if response else None

    # ---------------------------
    #   update
    # ---------------------------
    def update(self, path, param, value, mod_param, mod_value) -> bool:
        """Modify a parameter"""
        entry_found = False
        if not self._connected or not self._connection:
            if self._connection_epoch > time.time() - self._connection_retry_sec:
                return False

            if not self.connect():
                return False

        response = self.path(path)
        if response is None:
            return False

        for tmp in response:
            if param not in tmp:
                continue

            if tmp[param] != value:
                continue

            entry_found = True
            params = {".id": tmp[".id"], mod_param: mod_value}

            self.lock.acquire()
            try:
                response.update(**params)
            except librouteros_custom.exceptions.ConnectionClosed:
                if not self.connection_error_reported:
                    _LOGGER.error("Mikrotik %s connection closed", self._host)
                    self.connection_error_reported = True

                self.disconnect()
                self.lock.release()
                return False
            except (
                librouteros_custom.exceptions.TrapError,
                librouteros_custom.exceptions.MultiTrapError,
                librouteros_custom.exceptions.ProtocolError,
                librouteros_custom.exceptions.FatalError,
                ssl.SSLError,
                BrokenPipeError,
                OSError,
                ValueError,
            ) as api_error:
                if not self.connection_error_reported:
                    _LOGGER.error(
                        "Mikrotik %s error while update %s", self._host,
                        api_error
                    )
                    self.connection_error_reported = True

                self.disconnect()
                self.lock.release()
                return False
            except:
                if not self.connection_error_reported:
                    _LOGGER.error(
                        "Mikrotik %s error while update %s", self._host,
                        "unknown"
                    )
                    self.connection_error_reported = True

                self.disconnect()
                self.lock.release()
                return False

        self.lock.release()
        if not entry_found:
            error = f'Parameter "{param}" with value "{value}" not found'
            raise ApiEntryNotFound(error)

        return True

    # ---------------------------
    #   run_script
    # ---------------------------
    def run_script(self, name) -> bool:
        """Run script"""
        entry_found = False
        if not self._connected or not self._connection:
            if self._connection_epoch > time.time() - self._connection_retry_sec:
                return False

            if not self.connect():
                return False

        response = self.path("/system/script")
        if response is None:
            return False

        for tmp in response:
            if "name" not in tmp:
                continue

            if tmp["name"] != name:
                continue

            entry_found = True
            self.lock.acquire()
            try:
                run = response("run", **{".id": tmp[".id"]})
                tuple(run)
            except librouteros_custom.exceptions.ConnectionClosed:
                if not self.connection_error_reported:
                    _LOGGER.error("Mikrotik %s connection closed", self._host)
                    self.connection_error_reported = True

                self.disconnect()
                self.lock.release()
                return False
            except (
                librouteros_custom.exceptions.TrapError,
                librouteros_custom.exceptions.MultiTrapError,
                librouteros_custom.exceptions.ProtocolError,
                librouteros_custom.exceptions.FatalError,
                ssl.SSLError,
                BrokenPipeError,
                OSError,
                ValueError,
            ) as api_error:
                if not self.connection_error_reported:
                    _LOGGER.error(
                        "Mikrotik %s error while run_script %s", self._host,
                        api_error
                    )
                    self.connection_error_reported = True

                self.disconnect()
                self.lock.release()
                return False
            except:
                if not self.connection_error_reported:
                    _LOGGER.error(
                        "Mikrotik %s error while run_script %s", self._host,
                        "unknown"
                    )
                    self.connection_error_reported = True

                self.disconnect()
                self.lock.release()
                return False

        self.lock.release()
        if not entry_found:
            error = f'Script "{name}" not found'
            raise ApiEntryNotFound(error)

        return True

    # ---------------------------
    #   get_traffic
    # ---------------------------
    def get_traffic(self, interfaces) -> Optional(list):
        """Get traffic stats"""
        if not self._connected or not self._connection:
            if self._connection_epoch > time.time() - self._connection_retry_sec:
                return None

            if not self.connect():
                return None

        response = self.path("/interface")
        if response is None:
            return None

        args = {"interface": interfaces, "once": True}
        self.lock.acquire()
        try:
            traffic = response("monitor-traffic", **args)
            _LOGGER.debug(
                "API response (%s): %s", "/interface/monitor-traffic", traffic
            )
        except librouteros_custom.exceptions.ConnectionClosed:
            if not self.connection_error_reported:
                _LOGGER.error("Mikrotik %s connection closed", self._host)
                self.connection_error_reported = True

            self.disconnect()
            self.lock.release()
            return None
        except (
            librouteros_custom.exceptions.TrapError,
            librouteros_custom.exceptions.MultiTrapError,
            librouteros_custom.exceptions.ProtocolError,
            librouteros_custom.exceptions.FatalError,
            ssl.SSLError,
            BrokenPipeError,
            OSError,
            ValueError,
        ) as api_error:
            if not self.connection_error_reported:
                _LOGGER.error(
                    "Mikrotik %s error while get_traffic %s", self._host,
                    api_error
                )
                self.connection_error_reported = True

            self.disconnect()
            self.lock.release()
            return None
        except:
            if not self.connection_error_reported:
                _LOGGER.error(
                    "Mikrotik %s error while get_traffic %s", self._host,
                    "unknown"
                )
                self.connection_error_reported = True

            self.disconnect()
            self.lock.release()
            return None

        try:
            tuple(response)
        except librouteros_custom.exceptions.ConnectionClosed as api_error:
            if not self.connection_error_reported:
                _LOGGER.error(
                    "Mikrotik %s error while get_traffic %s", self._host,
                    api_error
                )
                self.connection_error_reported = True

            self.disconnect()
            self.lock.release()
            return None
        except:
            if not self.connection_error_reported:
                _LOGGER.error(
                    "Mikrotik %s error while get_traffic %s", self._host,
                    "unknown"
                )
                self.connection_error_reported = True

            self.disconnect()
            self.lock.release()
            return None

        self.lock.release()
        return traffic if traffic else None

    @staticmethod
    def _current_milliseconds():
        from time import time
        return int(round(time() * 1000))

    def is_accounting_enabled(self) -> bool:
        accounting = self.path("/ip/accounting", return_list=True)
        if accounting is None:
            return False

        for item in accounting:
            if 'enabled' not in item:
                continue
            if item['enabled']:
                return True
        return False

    def is_accounting_local_traffic_enabled(self) -> bool:
        accounting = self.path("/ip/accounting", return_list=True)
        if accounting is None:
            return False

        for item in accounting:
            if 'account-local-traffic' not in item:
                continue
            if item['account-local-traffic']:
                return True
        return False

    # ---------------------------
    #   take_accounting_snapshot
    #   Returns float -> period in seconds between last and current run
    # ---------------------------
    def take_accounting_snapshot(self) -> float:
        """Get accounting data"""
        if not self._connected or not self._connection:
            if self._connection_epoch > time.time() - self._connection_retry_sec:
                return 0

            if not self.connect():
                return 0

        accounting = self.path("/ip/accounting")

        self.lock.acquire()
        try:
            # Prepare command
            take = accounting('snapshot/take')
            # Run command on Mikrotik
            tuple(take)
        except librouteros_custom.exceptions.ConnectionClosed:
            if not self.connection_error_reported:
                _LOGGER.error("Mikrotik %s connection closed", self._host)
                self.connection_error_reported = True

            self.disconnect()
            self.lock.release()
            return 0
        except (
            librouteros_custom.exceptions.TrapError,
            librouteros_custom.exceptions.MultiTrapError,
            librouteros_custom.exceptions.ProtocolError,
            librouteros_custom.exceptions.FatalError,
            ssl.SSLError,
            BrokenPipeError,
            OSError,
            ValueError,
        ) as api_error:
            if not self.connection_error_reported:
                _LOGGER.error(
                    "Mikrotik %s error while take_accounting_snapshot %s -> %s - %s", self._host,
                    type(api_error), api_error.args
                )
                self.connection_error_reported = True

            self.disconnect()
            self.lock.release()
            return 0
        except Exception as e:
            if not self.connection_error_reported:
                _LOGGER.error(
                    "% -> %s error on %s host while take_accounting_snapshot",
                    type(e), e.args, self._host,
                )
                self.connection_error_reported = True

            self.disconnect()
            self.lock.release()
            return 0

        self.lock.release()

        # First request will be discarded because we cannot know when the last data was retrieved
        # prevents spikes in data
        if not self.accounting_last_run:
            self.accounting_last_run = self._current_milliseconds()
            return 0

        # Calculate time difference in seconds and return
        time_diff = self._current_milliseconds() - self.accounting_last_run
        self.accounting_last_run = self._current_milliseconds()
        return time_diff / 1000
