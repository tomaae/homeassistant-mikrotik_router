"""Mikrotik API for Mikrotik Router."""

from __future__ import annotations

import logging
import ssl
from time import monotonic, time
from threading import RLock
from voluptuous import Optional
from .const import (
    DEFAULT_LOGIN_METHOD,
    DEFAULT_ENCODING,
)
from .exceptions import ApiEntryNotFound

import librouteros
from librouteros.exceptions import MultiTrapError, TrapError

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
        ssl_verify=True,
        login_method=DEFAULT_LOGIN_METHOD,
        encoding=DEFAULT_ENCODING,
    ):
        """Initialize the Mikrotik Client."""
        self._host = host
        self._use_ssl = use_ssl
        self._ssl_verify = ssl_verify
        self._port = port
        self._username = username
        self._password = password
        self._login_method = login_method
        self._encoding = encoding
        self._ssl_wrapper = None
        # API operations can call query() or connect() while holding the lock.
        self.lock = RLock()

        self._connection = None
        self._connected = False
        self._reconnected = True
        self._connection_epoch = 0
        self._connection_retry_sec = 58
        self.error = None
        self.connection_error_reported = False
        self.client_traffic_last_run = None
        self.disable_health = False

        # Default ports
        if not self._port:
            self._port = 8729 if self._use_ssl else 8728

    # ---------------------------
    #   has_reconnected
    # ---------------------------
    def has_reconnected(self) -> bool:
        """Check if mikrotik has reconnected"""
        if self._reconnected:
            self._reconnected = False
            return True

        return False

    # ---------------------------
    #   connection_check
    # ---------------------------
    def connection_check(self) -> bool:
        """Check if mikrotik is connected"""
        if not self._connected or not self._connection:
            if self._connection_epoch > time() - self._connection_retry_sec:
                return False

            if not self.connect():
                return False

        return True

    # ---------------------------
    #   disconnect
    # ---------------------------
    def disconnect(self, location="unknown", error=None):
        """Disconnect from Mikrotik device."""
        if not error:
            error = "unknown"

        if not self.connection_error_reported:
            if location == "unknown":
                _LOGGER.error("Mikrotik %s connection closed", self._host)
            else:
                _LOGGER.error(
                    "Mikrotik %s error while %s : %s", self._host, location, error
                )

            self.connection_error_reported = True

        self._reconnected = False
        self._connected = False
        self._connection = None
        self._connection_epoch = 0

    # ---------------------------
    #   connect
    # ---------------------------
    def connect(self) -> bool:
        """Connect to Mikrotik device."""
        self.error = ""
        self._connected = False
        self._connection_epoch = time()

        kwargs = {
            "encoding": self._encoding,
            "port": self._port,
        }
        kwargs.update(self._login_kwargs())

        self.lock.acquire()
        try:
            if self._use_ssl:
                if self._ssl_wrapper is None:
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = False
                    if self._ssl_verify:
                        ssl_context.verify_mode = ssl.CERT_REQUIRED
                        ssl_context.verify_flags &= ~ssl.VERIFY_X509_STRICT
                    else:
                        ssl_context.verify_mode = ssl.CERT_NONE
                    self._ssl_wrapper = ssl_context.wrap_socket
                kwargs["ssl_wrapper"] = self._ssl_wrapper

            self._connection = librouteros.connect(
                self._host, self._username, self._password, **kwargs
            )
        except TypeError as e:
            # Retry only for login kwarg name mismatches between librouteros
            # 3.x (login_methods) and 4.x (login_method).
            error_text = str(e)
            if "login_method" not in error_text:
                if not self.connection_error_reported:
                    _LOGGER.error(
                        "Mikrotik %s error while connecting: %s",
                        self._host,
                        e,
                    )
                    self.connection_error_reported = True
                self.error_to_strings(error_text)
                self._connection = None
                self.lock.release()
                return False

            if not self._swap_login_kwarg(kwargs):
                if not self.connection_error_reported:
                    _LOGGER.error(
                        "Mikrotik %s librouteros API mismatch while connecting: %s",
                        self._host,
                        e,
                    )
                    self.connection_error_reported = True
                self.error = "librouteros_api_mismatch"
                self._connection = None
                self.lock.release()
                return False

            try:
                self._connection = librouteros.connect(
                    self._host, self._username, self._password, **kwargs
                )
            except Exception as retry_error:
                if not self.connection_error_reported:
                    _LOGGER.error(
                        "Mikrotik %s error while connecting: %s",
                        self._host,
                        retry_error,
                    )
                    self.connection_error_reported = True
                self.error_to_strings(f"{retry_error}")
                self._connection = None
                self.lock.release()
                return False
        except Exception as e:
            if not self.connection_error_reported:
                _LOGGER.error("Mikrotik %s error while connecting: %s", self._host, e)
                self.connection_error_reported = True

            self.error_to_strings(f"{e}")
            self._connection = None
            self.lock.release()
            return False

        if self.connection_error_reported:
            _LOGGER.warning("Mikrotik Reconnected to %s", self._host)
            self.connection_error_reported = False
        else:
            _LOGGER.debug("Mikrotik Connected to %s", self._host)

        self._connected = True
        self._reconnected = True
        self.lock.release()

        return self._connected

    # ---------------------------
    #   _login_callable
    # ---------------------------
    def _login_callable(self):
        """Resolve configured login method to a librouteros callable."""
        if callable(self._login_method):
            return self._login_method

        from librouteros.login import plain, token

        if self._login_method == "token":
            return token
        return plain

    # ---------------------------
    #   _librouteros_major
    # ---------------------------
    @staticmethod
    def _librouteros_major() -> int | None:
        """Return librouteros major version when available."""
        version = getattr(librouteros, "__version__", None)
        if not version:
            return None
        try:
            return int(str(version).split(".", maxsplit=1)[0])
        except (TypeError, ValueError):
            return None

    # ---------------------------
    #   _login_kwargs
    # ---------------------------
    def _login_kwargs(self) -> dict:
        """Build login kwargs compatible with librouteros 3.x and 4.x."""
        major = self._librouteros_major()
        # Prefer callables on 4.x / unknown; keep legacy string/value on 3.x.
        if major is None or major >= 4:
            return {"login_method": self._login_callable()}
        if isinstance(self._login_method, str):
            return {"login_methods": self._login_method}
        return {"login_methods": self._login_callable()}

    # ---------------------------
    #   _swap_login_kwarg
    # ---------------------------
    def _swap_login_kwarg(self, kwargs: dict) -> bool:
        """Swap login_method/login_methods when the installed library disagrees."""
        if "login_method" in kwargs:
            value = kwargs.pop("login_method")
            # 3.x historically accepted the configured string name.
            kwargs["login_methods"] = (
                self._login_method if isinstance(self._login_method, str) else value
            )
            return True
        if "login_methods" in kwargs:
            kwargs.pop("login_methods")
            kwargs["login_method"] = self._login_callable()
            return True
        return False

    # ---------------------------
    #   error_to_strings
    # ---------------------------
    def error_to_strings(self, error):
        """Translate error output to error string."""
        self.error = "cannot_connect"
        normalized_error = str(error).strip().casefold()
        if normalized_error in {
            "invalid user name or password",
            "invalid user name or password (6)",
            "invalid username or password",
        }:
            self.error = "wrong_login"

        if "unexpected keyword argument 'login_method" in error or (
            "unexpected keyword argument 'login_methods" in error
        ):
            self.error = "librouteros_api_mismatch"

        if "'str' object is not callable" in error:
            self.error = "librouteros_api_mismatch"

        if "ALERT_HANDSHAKE_FAILURE" in error:
            self.error = "ssl_handshake_failure"

        if "CERTIFICATE_VERIFY_FAILED" in error:
            self.error = "ssl_verify_failure"

    # ---------------------------
    #   connected
    # ---------------------------
    def connected(self) -> bool:
        """Return connected boolean."""
        return self._connected

    # ---------------------------
    #   query
    # ---------------------------
    def query(
        self,
        path,
        command=None,
        args=None,
        return_list=True,
        ignore_trap=False,
    ) -> Optional(list):
        """Retrieve data from Mikrotik API."""
        """Returns generator object, unless return_list passed as True"""
        if path == "/system/health" and self.disable_health:
            return None

        if args is None:
            args = {}

        if not self.connection_check():
            return None

        self.lock.acquire()
        try:
            _LOGGER.debug("API query: %s", path)
            response = self._connection.path(path)
        except (TrapError, MultiTrapError) as e:
            if ignore_trap:
                _LOGGER.debug("Optional API query %s unavailable: %s", path, e)
                self.lock.release()
                return None

            self.disconnect("path", e)
            self.lock.release()
            return None
        except Exception as e:
            self.disconnect("path", e)
            self.lock.release()
            return None

        if response and return_list and not command:
            try:
                response = list(response)
            except (TrapError, MultiTrapError) as e:
                if ignore_trap:
                    _LOGGER.debug("Optional API query %s unavailable: %s", path, e)
                    self.lock.release()
                    return None

                self.disconnect(f"building list for path {path}", e)
                self.lock.release()
                return None
            except Exception as e:
                if path == "/system/health" and "no such command prefix" in str(e):
                    self.disable_health = True
                    self.lock.release()
                    return None

                self.disconnect(f"building list for path {path}", e)
                self.lock.release()
                return None

        elif response and command:
            _LOGGER.debug("API query: %s, %s, %s", path, command, args)
            try:
                response = list(response(command, **args))
            except (TrapError, MultiTrapError) as e:
                if ignore_trap:
                    _LOGGER.debug("Optional API query %s unavailable: %s", path, e)
                    self.lock.release()
                    return None

                self.disconnect("path", e)
                self.lock.release()
                return None
            except Exception as e:
                self.disconnect("path", e)
                self.lock.release()
                return None

        self.lock.release()
        return response or None

    # ---------------------------
    #   set_value
    # ---------------------------
    def set_value(self, path, param, value, mod_param, mod_value) -> bool:
        """Modify a parameter"""
        # A librouteros path is lazy, so its lookup and update must share a lock.
        with self.lock:
            entry_found = None

            if not self.connection_check():
                return False

            response = self.query(path, return_list=False)
            if response is None:
                return False

            try:
                for tmp in response:
                    if param not in tmp:
                        continue

                    if tmp[param] != value:
                        continue

                    entry_found = tmp[".id"]

                if not entry_found:
                    raise ApiEntryNotFound(f"{param}={value}")

                response.update(**{".id": entry_found, mod_param: mod_value})
            except ApiEntryNotFound:
                raise
            except Exception as e:
                self.disconnect("set_value", e)
                return False

        return True

    # ---------------------------
    #   execute
    # ---------------------------
    def execute(self, path, command, param, value, attributes=None) -> bool:
        """Execute a command"""
        # Keep the optional lookup and command on the same socket transaction.
        with self.lock:
            entry_found = None
            params = {}

            if not self.connection_check():
                return False

            response = self.query(path, return_list=False)
            if response is None:
                return False

            try:
                if param:
                    for tmp in response:
                        if param not in tmp:
                            continue

                        if tmp[param] != value:
                            continue

                        entry_found = tmp[".id"]

                    if not entry_found:
                        raise ApiEntryNotFound(f"{param}={value}")

                    params = {".id": entry_found}

                if attributes:
                    params.update(attributes)

                tuple(response(command, **params))
            except ApiEntryNotFound:
                raise
            except Exception as e:
                self.disconnect("execute", e)
                return False

        return True

    # ---------------------------
    #   run_script
    # ---------------------------
    def run_script(self, name) -> bool:
        """Run script"""
        entry_found = None
        if not self.connection_check():
            return False

        response = self.query("/system/script", return_list=False)
        if response is None:
            return False

        self.lock.acquire()
        try:
            for tmp in response:
                if "name" not in tmp:
                    continue

                if tmp["name"] != name:
                    continue

                entry_found = tmp[".id"]

            if not entry_found:
                raise ApiEntryNotFound(f"script={name}")

            run = response("run", **{".id": entry_found})
            tuple(run)
        except ApiEntryNotFound:
            raise
        except Exception as e:
            self.disconnect("run_script", e)
            return False
        finally:
            self.lock.release()

        return True

    # ---------------------------
    #   arp_ping
    # ---------------------------
    def arp_ping(self, address, interface) -> bool:
        """Check arp ping response traffic stats"""
        if not self.connection_check():
            return False

        response = self.query("/ping", return_list=False)
        if response is None:
            return False

        args = {
            "arp-ping": "no",
            "interval": "100ms",
            "count": 3,
            "interface": interface,
            "address": address,
        }
        self.lock.acquire()
        try:
            # _LOGGER.debug("Ping host query: %s", args["address"])
            ping = response("/ping", **args)
        except Exception as e:
            self.disconnect("arp_ping", e)
            self.lock.release()
            return False

        try:
            ping = list(ping)
        except Exception as e:
            self.disconnect("arp_ping", e)
            self.lock.release()
            return False

        self.lock.release()

        for tmp in ping:
            if "received" in tmp and tmp["received"] > 0:
                _LOGGER.debug("Ping host success: %s", args["address"])
                return True

        _LOGGER.debug("Ping host failure: %s", args["address"])
        return False

    def is_accounting_and_local_traffic_enabled(self) -> (bool, bool):
        # Returns:
        #   1st bool: Is accounting enabled
        #   2nd bool: Is account-local-traffic enabled

        if not self.connection_check():
            return False, False

        response = self.query("/ip/accounting")
        if response is None:
            return False, False

        for item in response:
            if "enabled" not in item:
                continue
            if not item["enabled"]:
                return False, False

        for item in response:
            if "account-local-traffic" not in item:
                continue
            if not item["account-local-traffic"]:
                return True, False

        return True, True

    # ---------------------------
    #   take_client_traffic_snapshot
    #   Returns float -> period in seconds between last and current run
    # ---------------------------
    def take_client_traffic_snapshot(self, use_accounting) -> float:
        """Tako accounting snapshot and return time diff"""
        if not self.connection_check():
            return 0

        if use_accounting:
            accounting = self.query("/ip/accounting", return_list=False)

            self.lock.acquire()
            try:
                # Prepare command
                take = accounting("snapshot/take")
            except Exception as e:
                self.disconnect("accounting_snapshot", e)
                self.lock.release()
                return 0

            try:
                list(take)
            except Exception as e:
                self.disconnect("accounting_snapshot", e)
                self.lock.release()
                return 0

            self.lock.release()

        client_traffic_current_run = monotonic()

        # First request will be discarded because we cannot know when the last data was retrieved
        # prevents spikes in data
        if self.client_traffic_last_run is None:
            self.client_traffic_last_run = client_traffic_current_run
            return 0

        # Calculate time difference in seconds and return
        time_diff = client_traffic_current_run - self.client_traffic_last_run
        self.client_traffic_last_run = client_traffic_current_run
        return time_diff
