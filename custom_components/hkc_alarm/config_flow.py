"""Config flow for HKC Alarm."""
import logging
import voluptuous as vol
from pyhkc.hkc_api import HKCAlarm
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL, CONF_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class HKCAlarmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HKC Alarm."""

    VERSION = 3
    MINOR_VERSION = 0
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

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
                },
                options={
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow for this handler."""
        return HKCAlarmOptionsFlow()

class HKCAlarmOptionsFlow(config_entries.OptionsFlow):
    """Handle an options flow for HKC Alarm."""

    async def async_step_init(self, user_input=None):
        """Handle the options step."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        user_input = {
             CONF_UPDATE_INTERVAL: self.config_entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        }

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=DEFAULT_UPDATE_INTERVAL
                ): int,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(options_schema, user_input)
        )
