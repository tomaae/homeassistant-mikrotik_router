"""Config flow to configure Mikrotik Router."""

import logging
import voluptuous as vol
from homeassistant.core import callback
from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_POLL,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SSL,
)

from .const import (
    DOMAIN,
    CONF_TRACK_ARP,
    DEFAULT_TRACK_ARP,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)

from .exceptions import OldLibrouteros
from .mikrotikapi import MikrotikAPI

_LOGGER = logging.getLogger(__name__)

# ---------------------------
#   configured_instances
# ---------------------------
@callback
def configured_instances(hass):
    """Return a set of configured instances."""
    return set(
        entry.data[CONF_NAME] for entry in hass.config_entries.async_entries(DOMAIN)
    )


# ---------------------------
#   MikrotikControllerConfigFlow
# ---------------------------
class MikrotikControllerConfigFlow(ConfigFlow, domain=DOMAIN):
    """MikrotikControllerConfigFlow class"""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize MikrotikControllerConfigFlow."""
        return

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return MikrotikControllerOptionsFlowHandler(config_entry)

    async def async_step_import(self, user_input=None):
        """Occurs when a previously entry setup fails and is re-initiated."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            # Check if instance with this name already exists
            if user_input[CONF_NAME] in configured_instances(self.hass):
                errors["base"] = "name_exists"

            # Test connection
            try:
                api = MikrotikAPI(host=user_input["host"],
                                  username=user_input["username"],
                                  password=user_input["password"],
                                  port=user_input["port"],
                                  use_ssl=user_input["ssl"]
                                  )
            except OldLibrouteros:
                errors["base"] = "librouteros_invalid"
            else:
                if not api.connect():
                    errors[CONF_HOST] = api.error

            # Save instance
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input
                )

            return self._show_config_form(host=user_input["host"],
                                          username=user_input["username"],
                                          password=user_input["password"],
                                          port=user_input["port"],
                                          name=user_input["name"],
                                          use_ssl=user_input["ssl"],
                                          errors=errors
                                          )

        return self._show_config_form(errors=errors)

    # ---------------------------
    #   _show_config_form
    # ---------------------------
    def _show_config_form(self, host='10.0.0.1', username='admin', password='admin', port=0, name='Mikrotik', use_ssl=False, errors=None):
        """Show the configuration form to edit data."""
        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=host): str,
                vol.Required(CONF_USERNAME, default=username): str,
                vol.Required(CONF_PASSWORD, default=password): str,
                vol.Optional(CONF_PORT, default=port): int,
                vol.Optional(CONF_NAME, default=name): str,
                vol.Optional(CONF_SSL, default=use_ssl): bool,
            }),
            errors=errors,
        )


# ---------------------------
#   MikrotikControllerOptionsFlowHandler
# ---------------------------
class MikrotikControllerOptionsFlowHandler(OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_device_tracker(user_input)

    async def async_step_device_tracker(self, user_input=None):
        """Manage the device tracker options."""
        if user_input is not None:
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="device_tracker",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_TRACK_ARP,
                        default=self.config_entry.options.get(
                            CONF_TRACK_ARP, DEFAULT_TRACK_ARP
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): int,
                }
            ),
        )
