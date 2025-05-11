import logging
from pyhkc.hkc_api import HKCAlarm
from datetime import datetime, timezone, timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import Throttle
from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL, CONF_UPDATE_INTERVAL

_logger = logging.getLogger(__name__)

class HKCAlarmCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, hkc_alarm: HKCAlarm, update_interval) -> None:
        super().__init__(
            hass,
            _logger,
            config_entry=config_entry,
            name="hkc_alarm_data",
            update_interval=timedelta(seconds=update_interval),
        )
        self._last_update = datetime.min
        self._hkc_alarm = hkc_alarm
        self.panel_time_offset = None
        self.status = None
        self.panel_data = None
        # self.sensor_data = None

    async def _async_update_data(self):
        @Throttle(timedelta(seconds=30))
        def fetch_data():
            self.status = self._hkc_alarm.get_system_status()
            self.panel_data = self._hkc_alarm.get_panel()
            # self.sensor_data = self.hkc_alarm.get_all_inputs()

        try:
            now = datetime.now(timezone.utc)
            if now > self._last_update + timedelta(seconds=30):
                self._last_update = now
                await self.hass.async_add_executor_job(fetch_data)
            return self.status, self.panel_data #, self.sensor_data
        except Exception as e:
            _logger.error(f"Exception occurred while fetching HKC data: {e}")
            raise UpdateFailed(f"Failed to update: {e}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    panel_id = entry.data["panel_id"]
    panel_password = entry.data["panel_password"]
    user_code = entry.data["user_code"]

    hkc_alarm = await hass.async_add_executor_job(
        HKCAlarm, panel_id, panel_password, user_code
    )

    update_interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    alarm_coordinator = HKCAlarmCoordinator(hass, entry, hkc_alarm, update_interval)
    await alarm_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "hkc_alarm": hkc_alarm,
        "update_interval": update_interval,
        "alarm_coordinator": alarm_coordinator,
    }

    @callback
    def update_options(updated_entry: ConfigEntry) -> None:
        update_interval = updated_entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        hass.data[DOMAIN][updated_entry.entry_id]["update_interval"] = update_interval
        ## TODO: update active coordinator intervals

    entry.add_update_listener(update_options)

    await hass.config_entries.async_forward_entry_setups(
        entry, ["alarm_control_panel", "sensor"]
    )
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor", "alarm_control_panel"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
