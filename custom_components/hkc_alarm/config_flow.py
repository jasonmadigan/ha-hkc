"""Config flow for HKC Alarm."""
import logging
from pyhkc.hkc_api import HKCAlarm
from homeassistant import config_entries, exceptions
import voluptuous as vol

from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL, CONF_UPDATE_INTERVAL

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HKCAlarmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HKC Alarm."""

    VERSION = 2

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            alarm_code = user_input["alarm_code"]
            panel_password = user_input["panel_password"]
            panel_id = user_input["panel_id"]

            # Initialize the HKCAlarm class in the executor
            api = await self.hass.async_add_executor_job(
                HKCAlarm, panel_id, panel_password, alarm_code
            )

            # Using the new check_login method
            is_authenticated = await self.hass.async_add_executor_job(api.check_login)

            if not is_authenticated:
                errors["base"] = "invalid_auth"
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(
                        {
                            vol.Required("alarm_code"): str,
                            vol.Required("panel_password"): str,
                            vol.Required("panel_id"): str,
                        }
                    ),
                    errors=errors,
                )
            return self.async_create_entry(
                title="HKC Alarm",
                data={
                    "panel_id": panel_id,
                    "panel_password": panel_password,
                    "user_code": alarm_code,
                    CONF_UPDATE_INTERVAL: user_input[CONF_UPDATE_INTERVAL],  # include update_interval in the entry data
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("alarm_code"): str,
                    vol.Required("panel_password"): str,
                    vol.Required("panel_id"): str,
                    vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): int,  # include update_interval in the schema
                }
            ),
            errors=errors,
        )

    async def async_step_options(self, user_input=None):
        """Handle the options step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=self.entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                ): int,
            }
        )

        return self.async_show_form(
            step_id="options",
            data_schema=options_schema,
        )
