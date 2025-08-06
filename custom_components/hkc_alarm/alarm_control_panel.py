import asyncio
import logging
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN


_logger = logging.getLogger(__name__)


class HKCAlarmControlPanel(CoordinatorEntity, AlarmControlPanelEntity):
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )

    _attr_code_arm_required = False

    def __init__(self, hkc_alarm, device_info, alarm_coordinator):
        super().__init__(alarm_coordinator)
        self._hkc_alarm = hkc_alarm
        self._device_info = device_info
        self._state = None
        self._alarm_coordinator = alarm_coordinator

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return str(self._hkc_alarm.panel_id) + "panel"

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the alarm control panel."""
        if self._alarm_coordinator.panel_data is None:
            return None

        # Extract the desired attributes from self._coordinator.panel_data
        attributes = {
            "Green LED": self._alarm_coordinator.panel_data["greenLed"],
            "Red LED": self._alarm_coordinator.panel_data["redLed"],
            "Amber LED": self._alarm_coordinator.panel_data["amberLed"],
            "Cursor On": self._alarm_coordinator.panel_data["cursorOn"],
            "Cursor Index": self._alarm_coordinator.panel_data["cursorIndex"],
            "Display": self._alarm_coordinator.panel_data["display"],
            "Blink": self._alarm_coordinator.panel_data["blink"],
        }
        return attributes

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._hkc_alarm.panel_id)},
            "name": "HKC Alarm System",
            "manufacturer": "HKC",
            "model": "HKC Alarm",
            "sw_version": "1.0.0",
        }

    @property
    def name(self):
        return "HKC Alarm System"

    @property
    def available(self) -> bool:
        """Return True if alarm is available."""
        return (
            self._alarm_coordinator.panel_data is not None
            and "display" in self._alarm_coordinator.panel_data
        )

    async def _send_alarm_command(self, command_name: str, refresh_delay: int) -> None:
        """Send alarm command and check response."""
        if (alarm_command := getattr(self._hkc_alarm, command_name)) is None:
            raise RuntimeError(f"unknown alarm command {command_name}")
        res = await self.hass.async_add_executor_job(alarm_command)
        command_type = command_name.split("_")[0]
        match res.get("resultCode"):
            case 5:  # alarm command successful
                pass
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
                        translation_key=command_name,
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
        await self._send_alarm_command("disarm", 3)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self._send_alarm_command("arm_partset_a", 10)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        await self._send_alarm_command("arm_partset_b", 10)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._send_alarm_command("arm_fullset", 10)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        blocks = self._alarm_coordinator.status.get("blocks", [])

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
    hkc_alarm = hass.data[DOMAIN][entry.entry_id]["hkc_alarm"]
    alarm_coordinator = hass.data[DOMAIN][entry.entry_id]["alarm_coordinator"]

    device_info = {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": "HKC Alarm System",
        "manufacturer": "HKC",
    }
    async_add_entities(
        [HKCAlarmControlPanel(hkc_alarm, device_info, alarm_coordinator)],
        True,
    )
