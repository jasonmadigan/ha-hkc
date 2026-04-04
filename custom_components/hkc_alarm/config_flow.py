"""Config flow for HKC Alarm."""

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_ADDITIONAL_USER_CODES,
    CONF_REQUIRE_USER_PIN,
    CONF_UPDATE_INTERVAL,
    DEFAULT_REQUIRE_USER_PIN,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .helpers import (
    InvalidUserCodeError,
    normalize_configured_user_codes,
    parse_additional_user_codes,
    serialize_user_codes,
)
from .pyhkc_compat import build_hkc_alarm

_LOGGER = logging.getLogger(__name__)


def _get_user_schema(defaults: dict | None = None) -> vol.Schema:
    """Build the config flow schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required("alarm_code", default=defaults.get("alarm_code", "")): str,
            vol.Required(
                "panel_password", default=defaults.get("panel_password", "")
            ): str,
            vol.Required("panel_id", default=defaults.get("panel_id", "")): str,
            vol.Optional(
                CONF_ADDITIONAL_USER_CODES,
                default=defaults.get(CONF_ADDITIONAL_USER_CODES, ""),
            ): str,
            vol.Optional(
                CONF_REQUIRE_USER_PIN,
                default=defaults.get(CONF_REQUIRE_USER_PIN, DEFAULT_REQUIRE_USER_PIN),
            ): bool,
            vol.Optional(
                CONF_UPDATE_INTERVAL,
                default=defaults.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            ): int,
        }
    )


class HKCAlarmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HKC Alarm."""

    VERSION = 3
    MINOR_VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def _find_existing_entry_for_panel(
        self, panel_id: str
    ) -> config_entries.ConfigEntry | None:
        """Find any existing entry for the same panel."""
        for entry in self._async_current_entries():
            if entry.data.get("panel_id") == panel_id or entry.unique_id == panel_id:
                return entry
        return None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        defaults = user_input or {}

        if user_input is not None:
            panel_id = user_input["panel_id"].strip()
            panel_password = user_input["panel_password"].strip()
            alarm_code = user_input["alarm_code"].strip()

            try:
                user_codes = normalize_configured_user_codes(
                    alarm_code,
                    user_input.get(CONF_ADDITIONAL_USER_CODES),
                )
            except InvalidUserCodeError:
                errors["base"] = "invalid_user_codes"
            else:
                api = await self.hass.async_add_executor_job(
                    build_hkc_alarm,
                    panel_id,
                    panel_password,
                    alarm_code,
                    user_codes[1:],
                )

                is_authenticated = await self.hass.async_add_executor_job(api.check_login)

                if not is_authenticated:
                    errors["base"] = "invalid_auth"
                else:
                    if self._find_existing_entry_for_panel(panel_id) is not None:
                        return self.async_abort(reason="already_configured")
                    await self.async_set_unique_id(panel_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=f"HKC Alarm {panel_id}",
                        data={
                            "panel_id": panel_id,
                            "panel_password": panel_password,
                            "user_code": alarm_code,
                        },
                        options={
                            CONF_UPDATE_INTERVAL: user_input[CONF_UPDATE_INTERVAL],
                            CONF_ADDITIONAL_USER_CODES: user_codes[1:],
                            CONF_REQUIRE_USER_PIN: bool(
                                user_input.get(
                                    CONF_REQUIRE_USER_PIN, DEFAULT_REQUIRE_USER_PIN
                                )
                            ),
                        },
                    )

            defaults = {
                **user_input,
                "panel_id": panel_id,
                "panel_password": panel_password,
                "alarm_code": alarm_code,
            }

        return self.async_show_form(
            step_id="user",
            data_schema=_get_user_schema(defaults),
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
        errors = {}
        defaults = user_input or {
            CONF_UPDATE_INTERVAL: self.config_entry.options.get(
                CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
            ),
            CONF_ADDITIONAL_USER_CODES: serialize_user_codes(
                parse_additional_user_codes(
                    self.config_entry.options.get(CONF_ADDITIONAL_USER_CODES, [])
                )
            ),
            CONF_REQUIRE_USER_PIN: self.config_entry.options.get(
                CONF_REQUIRE_USER_PIN, DEFAULT_REQUIRE_USER_PIN
            ),
        }

        if user_input is not None:
            try:
                configured_codes = normalize_configured_user_codes(
                    self.config_entry.data["user_code"],
                    user_input.get(CONF_ADDITIONAL_USER_CODES),
                )
            except InvalidUserCodeError:
                errors["base"] = "invalid_user_codes"
            else:
                return self.async_create_entry(
                    data={
                        CONF_UPDATE_INTERVAL: user_input[CONF_UPDATE_INTERVAL],
                        CONF_ADDITIONAL_USER_CODES: configured_codes[1:],
                        CONF_REQUIRE_USER_PIN: bool(
                            user_input.get(
                                CONF_REQUIRE_USER_PIN, DEFAULT_REQUIRE_USER_PIN
                            )
                        ),
                    }
                )

        options_schema = vol.Schema(
            {
                vol.Optional(CONF_ADDITIONAL_USER_CODES, default=""): str,
                vol.Optional(
                    CONF_REQUIRE_USER_PIN,
                    default=DEFAULT_REQUIRE_USER_PIN,
                ): bool,
                vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): int,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(options_schema, defaults),
            errors=errors,
        )
