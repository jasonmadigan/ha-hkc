from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from .const import DOMAIN
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
    UpdateFailed,
)
from datetime import timedelta
from .const import DOMAIN, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL

import logging

from datetime import timedelta
from homeassistant.core import callback


_logger = logging.getLogger(__name__)


class HKCAlarmControlPanel(AlarmControlPanelEntity, CoordinatorEntity):
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )

    _attr_code_arm_required = False

    def __init__(self, data, device_info, coordinator):
        AlarmControlPanelEntity.__init__(self)
        CoordinatorEntity.__init__(self, coordinator)
        self._hkc_alarm = data.get('hkc_alarm')
        self._scan_interval = data.get('scan_interval')
        self._device_info = device_info
        self._state = None
        self._panel_data = None

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return str(self._hkc_alarm.panel_id) + "panel"

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the alarm control panel."""
        if self._panel_data is None:
            return None

        # Extract the desired attributes from self._panel_data
        attributes = {
            "Green LED": self._panel_data['greenLed'],
            "Red LED": self._panel_data['redLed'],
            "Amber LED": self._panel_data['amberLed'],
            "Cursor On": self._panel_data['cursorOn'],
            "Cursor Index": self._panel_data['cursorIndex'],
            "Display": self._panel_data['display'],
            "Blink": self._panel_data['blink'],
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
    def state(self):
        return self._state

    @property
    def name(self):
        return "HKC Alarm System"

    @property
    def available(self) -> bool:
        """Return True if alarm is available."""
        return self._panel_data is not None and "display" in self._panel_data

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self.hass.async_add_executor_job(self._hkc_alarm.disarm)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self.hass.async_add_executor_job(self._hkc_alarm.arm_partset_a)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        await self.hass.async_add_executor_job(self._hkc_alarm.arm_partset_b)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self.hass.async_add_executor_job(self._hkc_alarm.arm_fullset)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        status, panel_data = self.coordinator.data
        self._panel_data = panel_data
        blocks = status.get("blocks", [])

        if any(block["inAlarm"] for block in blocks):
            self._state = "triggered"
        elif any(block["armState"] == 3 for block in blocks):
            self._state = "armed_away"
        elif any(block["armState"] == 2 for block in blocks):
            self._state = "armed_night"
        elif any(block["armState"] == 1 for block in blocks):
            self._state = "armed_home"
        else:
            self._state = "disarmed"

        self.async_write_ha_state()  # Update the state with the latest data


async def async_setup_entry(hass, entry, async_add_entities):
    hkc_alarm = hass.data[DOMAIN][entry.entry_id]
    update_interval = entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)

    async def _async_fetch_data():
        try:
            hkc_alarm = hass.data[DOMAIN][entry.entry_id]["hkc_alarm"]
            status = await hass.async_add_executor_job(hkc_alarm.get_system_status)
            panel_data = await hass.async_add_executor_job(hkc_alarm.get_panel)
            return status, panel_data
        except Exception as e:
            _logger.error(f"Exception occurred while fetching data: {e}")
            raise UpdateFailed(f"Failed to update: {e}")


    coordinator = DataUpdateCoordinator(
        hass,
        _logger,
        name="hkc_alarm_data",
        update_method=_async_fetch_data,
        update_interval=timedelta(seconds=update_interval),
    )

    await coordinator.async_config_entry_first_refresh()

    device_info = {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": "HKC Alarm System",
        "manufacturer": "HKC",
    }
    async_add_entities(
        [HKCAlarmControlPanel(hkc_alarm, device_info, coordinator)],
        True,
    )
