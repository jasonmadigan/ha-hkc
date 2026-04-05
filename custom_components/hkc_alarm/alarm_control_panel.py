import asyncio
import logging
from datetime import datetime, timezone

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EVENT_ALARM_COMMAND_EXECUTED
from .pyhkc_compat import build_block_alarm_command


_logger = logging.getLogger(__name__)


class HKCAlarmControlPanel(CoordinatorEntity, AlarmControlPanelEntity):
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )

    _attr_code_arm_required = False

    def __init__(
        self,
        hkc_alarm,
        view,
        alarm_coordinator,
        require_user_pin,
    ):
        super().__init__(alarm_coordinator)
        self._hkc_alarm = hkc_alarm
        self._view = view
        self._alarm_coordinator = alarm_coordinator
        self._configured_user_codes = [str(code) for code in view["allowed_user_codes"]]
        self._primary_user_code = str(view["user_code"])
        self._require_user_pin = require_user_pin
        self._block_numbers = list(view["block_numbers"])
        self._last_command = None
        self._last_command_at = None
        self._last_command_state = None
        self._last_command_result = None

        self._attr_has_entity_name = True
        self._attr_name = None if not view["multi_view"] else view["label"]
        self._attr_code_arm_required = self._requires_user_pin
        self._attr_code_format = CodeFormat.NUMBER if self._shows_keypad else None

    @property
    def _shows_keypad(self) -> bool:
        return self._require_user_pin

    @property
    def _requires_user_pin(self) -> bool:
        return self._shows_keypad

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        if not self._view["multi_view"]:
            return str(self._hkc_alarm.panel_id) + "panel"
        return f"{self._hkc_alarm.panel_id}panel_{self._view['key']}"

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the alarm control panel."""
        if self._alarm_coordinator.panel_data is None:
            return None

        entry_data = {}
        if getattr(self, "hass", None) is not None and self.coordinator.config_entry is not None:
            entry_data = self.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]
        metadata = entry_data.get("device_metadata", {})
        temporary_user = entry_data.get("temporary_user_by_code", {}).get(self._primary_user_code, {})
        attributes = {
            "Green LED": self._alarm_coordinator.panel_data["greenLed"],
            "Red LED": self._alarm_coordinator.panel_data["redLed"],
            "Amber LED": self._alarm_coordinator.panel_data["amberLed"],
            "Cursor On": self._alarm_coordinator.panel_data["cursorOn"],
            "Cursor Index": self._alarm_coordinator.panel_data["cursorIndex"],
            "Display": self._alarm_coordinator.panel_data["display"],
            "Blink": self._alarm_coordinator.panel_data["blink"],
        }
        if metadata.get("panel_name"):
            attributes["Panel Name"] = metadata["panel_name"]
        if metadata.get("installation_name"):
            attributes["Installation Name"] = metadata["installation_name"]
        if metadata.get("site_name"):
            attributes["Site Name"] = metadata["site_name"]
        if metadata.get("output_count") is not None:
            attributes["Output Count"] = metadata["output_count"]
        if "subscriptionDaysLeft" in temporary_user:
            attributes["Temporary User Subscription Days Left"] = temporary_user[
                "subscriptionDaysLeft"
            ]
        if self._block_numbers:
            attributes["Blocks"] = self._block_numbers
        if self._last_command is not None:
            attributes["Last Command"] = self._last_command
        if self._last_command_state is not None:
            attributes["Last Command State"] = self._last_command_state.value
        if self._last_command_result is not None:
            attributes["Last Command Result"] = self._last_command_result
        if self._last_command_at is not None:
            attributes["Last Command At"] = self._last_command_at.isoformat()
        return attributes

    @property
    def device_info(self):
        entry_data = {}
        if getattr(self, "hass", None) is not None and self.coordinator.config_entry is not None:
            entry_data = self.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]
        metadata = entry_data.get("device_metadata", {})
        identifier = (
            (DOMAIN, self._hkc_alarm.panel_id)
            if not self._view["multi_view"]
            else (DOMAIN, f"{self._hkc_alarm.panel_id}_{self._view['key']}")
        )
        return {
            "identifiers": {identifier},
            "name": self._view["label"],
            "manufacturer": "HKC",
            "model": metadata.get("model", "HKC Alarm"),
            "sw_version": metadata.get("sw_version", "1.0.0"),
            "serial_number": metadata.get("serial_number"),
        }

    @property
    def available(self) -> bool:
        """Return True if alarm is available."""
        return (
            self._alarm_coordinator.panel_data is not None
            and "display" in self._alarm_coordinator.panel_data
        )

    def _resolve_command_user_code(self, code: str | None) -> str:
        user_code = (code or "").strip()
        if not user_code:
            if self._requires_user_pin:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="code_required",
                )
            return self._primary_user_code

        if user_code not in self._configured_user_codes:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_user_code",
            )

        return user_code

    def _state_for_command(self, command_name: str) -> AlarmControlPanelState | None:
        return {
            "disarm": AlarmControlPanelState.DISARMED,
            "arm_partset_a": AlarmControlPanelState.ARMED_HOME,
            "arm_partset_b": AlarmControlPanelState.ARMED_NIGHT,
            "arm_fullset": AlarmControlPanelState.ARMED_AWAY,
        }.get(command_name)

    def _update_command_feedback(self, command_name: str, user_code: str) -> None:
        self._last_command = command_name
        self._last_command_at = datetime.now(timezone.utc)
        self._last_command_state = self._state_for_command(command_name)
        self._last_command_result = "success"

        if getattr(self, "hass", None) is not None:
            self.hass.bus.async_fire(
                EVENT_ALARM_COMMAND_EXECUTED,
                {
                    "entity_id": self.entity_id,
                    "command": command_name,
                    "result": self._last_command_result,
                    "state": self._last_command_state.value
                    if self._last_command_state is not None
                    else None,
                    "user_code": user_code,
                },
            )

        self.async_write_ha_state()

    async def _send_alarm_command(
        self,
        command_name: str,
        refresh_delay: int,
        code: str | None,
    ) -> None:
        """Send alarm command and check response."""
        if (alarm_command := getattr(self._hkc_alarm, command_name)) is None:
            raise RuntimeError(f"unknown alarm command {command_name}")
        user_code = self._resolve_command_user_code(code)
        try:
            command = build_block_alarm_command(
                self._hkc_alarm,
                command_name,
                user_code,
                self._primary_user_code,
                self._block_numbers[0] if len(self._block_numbers) == 1 else None,
            )
        except TypeError:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="block_commands_not_supported",
            ) from None
        res = await self.hass.async_add_executor_job(command)
        command_type = command_name.split("_")[0]
        match res.get("resultCode"):
            case 5:  # alarm command successful
                self._update_command_feedback(command_name, user_code)
            case 4:  # alarm is already in current state
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key=f"already_{command_type}ed"
                )
            case _:
                if error_list := res.get("errorList"):
                    error_msg = ", ".join(map(lambda x: x.get("description"), error_list))
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key=f"{command_name}_error",
                        translation_placeholders={"error_msg": error_msg},
                    )
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="unknown_response",
                    translation_placeholders={"response": res},
                )

        # Refresh alarm status on successful command
        if refresh_delay:
            await asyncio.sleep(refresh_delay)
            await self._alarm_coordinator.async_force_refresh()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self._send_alarm_command("disarm", 3, code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self._send_alarm_command("arm_partset_a", 10, code)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        await self._send_alarm_command("arm_partset_b", 10, code)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._send_alarm_command("arm_fullset", 10, code)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        status = self._alarm_coordinator.status_by_user.get(
            self._primary_user_code,
            self._alarm_coordinator.status,
        )
        blocks = status.get("blocks", [])
        if self._block_numbers:
            selected_blocks = []
            for block_number in self._block_numbers:
                index = block_number - 1
                if 0 <= index < len(blocks):
                    selected_blocks.append(blocks[index])
            blocks = selected_blocks

        if any(block["inAlarm"] for block in blocks):
            self._attr_alarm_state = AlarmControlPanelState.TRIGGERED
        elif any(block["armState"] == 3 for block in blocks):
            self._attr_alarm_state = AlarmControlPanelState.ARMED_AWAY
        elif any(block["armState"] == 2 for block in blocks):
            self._attr_alarm_state = AlarmControlPanelState.ARMED_NIGHT
        elif any(block["armState"] == 1 for block in blocks):
            self._attr_alarm_state = AlarmControlPanelState.ARMED_HOME
        else:
            self._attr_alarm_state = AlarmControlPanelState.DISARMED

        self.async_write_ha_state()  # Update the state with the latest data


async def async_setup_entry(hass, entry, async_add_entities):
    entry_data = hass.data[DOMAIN][entry.entry_id]
    hkc_alarm = entry_data["hkc_alarm"]
    alarm_coordinator = entry_data["alarm_coordinator"]
    async_add_entities(
        [
            HKCAlarmControlPanel(
                hkc_alarm,
                view,
                alarm_coordinator,
                entry_data["require_user_pin"],
            )
            for view in entry_data["views"]
        ],
        True,
    )
