"""Config flow to configure Mikrotik Router."""

import logging

import voluptuous as vol
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
    CONF_VERIFY_SSL,
    UnitOfTime,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_TRACK_IFACE_CLIENTS,
    DEFAULT_TRACK_IFACE_CLIENTS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    CONF_DEVICE_TRACKER_SCAN_INTERVAL,
    DEFAULT_DEVICE_TRACKER_SCAN_INTERVAL,
    CONF_TRACK_HOSTS,
    DEFAULT_TRACK_HOSTS,
    CONF_SENSOR_PORT_TRACKER,
    DEFAULT_SENSOR_PORT_TRACKER,
    CONF_SENSOR_PORT_TRAFFIC,
    DEFAULT_SENSOR_PORT_TRAFFIC,
    CONF_SENSOR_CLIENT_TRAFFIC,
    DEFAULT_SENSOR_CLIENT_TRAFFIC,
    CONF_SENSOR_CLIENT_CAPTIVE,
    DEFAULT_SENSOR_CLIENT_CAPTIVE,
    CONF_SENSOR_SIMPLE_QUEUES,
    DEFAULT_SENSOR_SIMPLE_QUEUES,
    CONF_SENSOR_NAT,
    DEFAULT_SENSOR_NAT,
    CONF_SENSOR_MANGLE,
    DEFAULT_SENSOR_MANGLE,
    CONF_SENSOR_FILTER,
    DEFAULT_SENSOR_FILTER,
    CONF_SENSOR_KIDCONTROL,
    DEFAULT_SENSOR_KIDCONTROL,
    CONF_SENSOR_PPP,
    DEFAULT_SENSOR_PPP,
    CONF_SENSOR_SCRIPTS,
    DEFAULT_SENSOR_SCRIPTS,
    CONF_SENSOR_ENVIRONMENT,
    DEFAULT_SENSOR_ENVIRONMENT,
    CONF_TRACK_HOSTS_TIMEOUT,
    DEFAULT_TRACK_HOST_TIMEOUT,
    DEFAULT_HOST,
    DEFAULT_USERNAME,
    DEFAULT_PORT,
    DEFAULT_DEVICE_NAME,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DEFAULT_SENSOR_NETWATCH_TRACKER,
    CONF_SENSOR_NETWATCH_TRACKER,
)
from .helper import router_unique_id
from .mikrotikapi import MikrotikAPI

_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   validate_input
# ---------------------------
def validate_input(user_input):
    """Validate connection settings and identify the router."""
    api = MikrotikAPI(
        host=user_input[CONF_HOST],
        username=user_input[CONF_USERNAME],
        password=user_input[CONF_PASSWORD],
        port=user_input[CONF_PORT],
        use_ssl=user_input[CONF_SSL],
        ssl_verify=user_input[CONF_VERIFY_SSL],
    )
    try:
        return _validate_with_api(api, user_input)
    finally:
        api.close()


# ---------------------------
#   _validate_with_api
# ---------------------------
def _validate_with_api(api, user_input):
    """Validate the connection using an API client the caller closes."""
    if not api.connect():
        return None, "invalid_auth" if api.error == "wrong_login" else api.error

    resource = api.query("/system/resource")
    if not api.connected():
        return None, api.error or "cannot_connect"

    board_name = ""
    if resource:
        board_name = str(resource[0].get("board-name", "")).strip().casefold()

    serial_number = None
    software_id = None
    system_id = None
    if board_name.startswith("chr"):
        license_data = api.query(
            "/system/license",
            command="print",
            args={".proplist": "system-id"},
            ignore_trap=True,
        )
        if not api.connected():
            return None, api.error or "cannot_connect"
        if license_data:
            system_id = license_data[0].get("system-id")
    elif board_name.startswith("x86"):
        license_data = api.query(
            "/system/license",
            command="print",
            args={".proplist": "software-id"},
            ignore_trap=True,
        )
        if not api.connected():
            return None, api.error or "cannot_connect"
        if license_data:
            software_id = license_data[0].get("software-id")
    else:
        routerboard = api.query("/system/routerboard")
        if not api.connected():
            return None, api.error or "cannot_connect"
        if routerboard:
            serial_number = routerboard[0].get("serial-number")

    return (
        router_unique_id(
            user_input[CONF_HOST],
            user_input[CONF_PORT],
            user_input[CONF_SSL],
            serial_number=serial_number,
            software_id=software_id,
            system_id=system_id,
        ),
        None,
    )


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

    VERSION = 3
    MINOR_VERSION = 3
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize MikrotikControllerConfigFlow."""

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return MikrotikControllerOptionsFlowHandler()

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
            else:
                unique_id, error = await self.hass.async_add_executor_job(
                    validate_input, user_input
                )
                if error:
                    errors["base"] = error
                else:
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

            # Save instance
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

            return self._show_config_form(user_input=user_input, errors=errors)

        return self._show_config_form(
            user_input={
                CONF_NAME: DEFAULT_DEVICE_NAME,
                CONF_HOST: DEFAULT_HOST,
                CONF_USERNAME: DEFAULT_USERNAME,
                CONF_PASSWORD: DEFAULT_USERNAME,
                CONF_PORT: DEFAULT_PORT,
                CONF_SSL: DEFAULT_SSL,
                CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
            },
            errors=errors,
        )

    async def async_step_reauth(self, entry_data):
        """Start reauthentication for an existing entry."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Validate and save replacement credentials."""
        config_entry = self._get_reauth_entry()
        errors = {}

        if user_input is not None:
            updated_data = {**config_entry.data, **user_input}
            unique_id, error = await self.hass.async_add_executor_job(
                validate_input, updated_data
            )
            if error:
                errors["base"] = error
            else:
                identity_error = await self._async_validate_entry_identity(
                    config_entry, unique_id
                )
                if identity_error:
                    errors["base"] = identity_error
                else:
                    return self._update_entry_and_abort(
                        config_entry, user_input, unique_id
                    )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=config_entry.data[CONF_USERNAME],
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={"name": config_entry.title},
        )

    async def async_step_reconfigure(self, user_input=None):
        """Update connection settings for an existing entry."""
        config_entry = self._get_reconfigure_entry()
        errors = {}

        if user_input is not None:
            data_updates = dict(user_input)
            if not data_updates.get(CONF_PASSWORD):
                data_updates.pop(CONF_PASSWORD, None)
            updated_data = {**config_entry.data, **data_updates}
            unique_id, error = await self.hass.async_add_executor_job(
                validate_input, updated_data
            )
            if error:
                errors["base"] = error
            else:
                identity_error = await self._async_validate_entry_identity(
                    config_entry, unique_id
                )
                if identity_error:
                    errors["base"] = identity_error
                else:
                    return self._update_entry_and_abort(
                        config_entry, data_updates, unique_id
                    )

        return self._show_reconfigure_form(config_entry, errors)

    async def _async_validate_entry_identity(self, config_entry, unique_id):
        """Ensure recovery settings do not select a different known router."""
        await self.async_set_unique_id(unique_id)
        if config_entry.unique_id and not config_entry.unique_id.startswith(
            "endpoint:"
        ):
            if unique_id.startswith("endpoint:"):
                return "cannot_identify"
            self._abort_if_unique_id_mismatch(reason="wrong_router")
        elif config_entry.unique_id != unique_id:
            self._abort_if_unique_id_configured()
        return None

    def _update_entry_and_abort(self, config_entry, data_updates, unique_id):
        """Update an entry and ensure the changed configuration is loaded."""
        if config_entry.update_listeners:
            return self.async_update_and_abort(
                config_entry,
                data_updates=data_updates,
                unique_id=unique_id,
            )
        return self.async_update_reload_and_abort(
            config_entry,
            data_updates=data_updates,
            unique_id=unique_id,
        )

    # ---------------------------
    #   _show_config_form
    # ---------------------------
    def _show_config_form(self, user_input, errors=None):
        """Show the configuration form to edit data."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=user_input[CONF_NAME]): str,
                    vol.Required(CONF_HOST, default=user_input[CONF_HOST]): str,
                    vol.Required(CONF_USERNAME, default=user_input[CONF_USERNAME]): str,
                    vol.Required(CONF_PASSWORD, default=user_input[CONF_PASSWORD]): str,
                    vol.Optional(CONF_PORT, default=user_input[CONF_PORT]): int,
                    vol.Optional(CONF_SSL, default=user_input[CONF_SSL]): bool,
                    vol.Optional(
                        CONF_VERIFY_SSL, default=user_input[CONF_VERIFY_SSL]
                    ): bool,
                }
            ),
            errors=errors,
        )

    # ---------------------------
    #   _show_reconfigure_form
    # ---------------------------
    def _show_reconfigure_form(self, config_entry, errors=None):
        """Show the form used to edit connection settings."""
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=config_entry.data[CONF_HOST]): str,
                    vol.Required(
                        CONF_USERNAME, default=config_entry.data[CONF_USERNAME]
                    ): str,
                    vol.Optional(CONF_PASSWORD): str,
                    vol.Optional(CONF_PORT, default=config_entry.data[CONF_PORT]): int,
                    vol.Optional(CONF_SSL, default=config_entry.data[CONF_SSL]): bool,
                    vol.Optional(
                        CONF_VERIFY_SSL,
                        default=config_entry.data[CONF_VERIFY_SSL],
                    ): bool,
                }
            ),
            errors=errors,
        )


# ---------------------------
#   MikrotikControllerOptionsFlowHandler
# ---------------------------
class MikrotikControllerOptionsFlowHandler(OptionsFlow):
    """Handle options.

    Do not override ``__init__`` or assign ``config_entry``; Home Assistant sets
    ``config_entry`` on the flow instance.
    """

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        self.options = dict(self.config_entry.options)
        return await self.async_step_basic_options(user_input)

    async def async_step_basic_options(self, user_input=None):
        """Manage the basic options options."""
        if user_input is not None:
            self.options.update(user_input)
            return await self.async_step_sensor_select()

        return self.async_show_form(
            step_id="basic_options",
            last_step=False,
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=10,
                            max=600,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement=UnitOfTime.SECONDS,
                        ),
                    ),
                    vol.Optional(
                        CONF_DEVICE_TRACKER_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_DEVICE_TRACKER_SCAN_INTERVAL,
                            DEFAULT_DEVICE_TRACKER_SCAN_INTERVAL,
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=10,
                            max=600,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement=UnitOfTime.SECONDS,
                        ),
                    ),
                    vol.Optional(
                        CONF_TRACK_IFACE_CLIENTS,
                        default=self.config_entry.options.get(
                            CONF_TRACK_IFACE_CLIENTS, DEFAULT_TRACK_IFACE_CLIENTS
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_TRACK_HOSTS_TIMEOUT,
                        default=self.config_entry.options.get(
                            CONF_TRACK_HOSTS_TIMEOUT, DEFAULT_TRACK_HOST_TIMEOUT
                        ),
                    ): int,
                }
            ),
        )

    async def async_step_sensor_select(self, user_input=None):
        """Manage the sensor select options."""
        if user_input is not None:
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="sensor_select",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SENSOR_PORT_TRACKER,
                        default=self.config_entry.options.get(
                            CONF_SENSOR_PORT_TRACKER, DEFAULT_SENSOR_PORT_TRACKER
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_SENSOR_PORT_TRAFFIC,
                        default=self.config_entry.options.get(
                            CONF_SENSOR_PORT_TRAFFIC, DEFAULT_SENSOR_PORT_TRAFFIC
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_TRACK_HOSTS,
                        default=self.config_entry.options.get(
                            CONF_TRACK_HOSTS, DEFAULT_TRACK_HOSTS
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_SENSOR_CLIENT_TRAFFIC,
                        default=self.config_entry.options.get(
                            CONF_SENSOR_CLIENT_TRAFFIC, DEFAULT_SENSOR_CLIENT_TRAFFIC
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_SENSOR_CLIENT_CAPTIVE,
                        default=self.config_entry.options.get(
                            CONF_SENSOR_CLIENT_CAPTIVE, DEFAULT_SENSOR_CLIENT_CAPTIVE
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_SENSOR_SIMPLE_QUEUES,
                        default=self.config_entry.options.get(
                            CONF_SENSOR_SIMPLE_QUEUES, DEFAULT_SENSOR_SIMPLE_QUEUES
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_SENSOR_NAT,
                        default=self.config_entry.options.get(
                            CONF_SENSOR_NAT, DEFAULT_SENSOR_NAT
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_SENSOR_MANGLE,
                        default=self.config_entry.options.get(
                            CONF_SENSOR_MANGLE, DEFAULT_SENSOR_MANGLE
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_SENSOR_FILTER,
                        default=self.config_entry.options.get(
                            CONF_SENSOR_FILTER, DEFAULT_SENSOR_FILTER
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_SENSOR_KIDCONTROL,
                        default=self.config_entry.options.get(
                            CONF_SENSOR_KIDCONTROL, DEFAULT_SENSOR_KIDCONTROL
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_SENSOR_NETWATCH_TRACKER,
                        default=self.config_entry.options.get(
                            CONF_SENSOR_NETWATCH_TRACKER,
                            DEFAULT_SENSOR_NETWATCH_TRACKER,
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_SENSOR_PPP,
                        default=self.config_entry.options.get(
                            CONF_SENSOR_PPP, DEFAULT_SENSOR_PPP
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_SENSOR_SCRIPTS,
                        default=self.config_entry.options.get(
                            CONF_SENSOR_SCRIPTS, DEFAULT_SENSOR_SCRIPTS
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_SENSOR_ENVIRONMENT,
                        default=self.config_entry.options.get(
                            CONF_SENSOR_ENVIRONMENT, DEFAULT_SENSOR_ENVIRONMENT
                        ),
                    ): bool,
                },
            ),
        )
