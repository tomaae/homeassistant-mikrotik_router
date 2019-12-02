"""Mikrotik API for Mikrotik Router."""

import ssl
import logging
import librouteros
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
        
        # Default ports
        if not self._port:
            self._port = 8729 if self._use_ssl else 8728
    
    # ---------------------------
    #   connect
    # ---------------------------
    def connect(self):
        """Connect to Mikrotik device."""
        self.error = ""
        self._connected = False
        
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
