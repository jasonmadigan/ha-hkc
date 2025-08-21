import logging
import traceback
from pyhkc.hkc_api import HKCAlarm
from datetime import datetime, timezone, timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .config_flow import HKCAlarmConfigFlow
from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL, CONF_UPDATE_INTERVAL, MIN_UPDATE_INTERVAL

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
        self._last_update = None
        self._hkc_alarm = hkc_alarm
        self.panel_time = None
        self._panel_time_delta = timedelta()
        self.status = None
        self.panel_data = None
        # self.sensor_data = None

    async def async_force_refresh(self):
        """Force refresh alarm coordinator, ignoring debounce."""
        self._last_update = None
        return await self.async_refresh()

    async def _async_update_data(self):
        def fetch_data():
            self.status = self._hkc_alarm.get_system_status()
            self.panel_data = self._hkc_alarm.get_panel()
            # self.sensor_data = self.hkc_alarm.get_all_inputs()

        def parse_panel_time():
            panel_time_str = self.panel_data.get("display", "")
            now = datetime.now(timezone.utc)
            try:
                self.panel_time = datetime.strptime(
                    panel_time_str, "%a %d %b %H:%M"
                ).replace(year=now.year, tzinfo=timezone.utc)
                self._panel_time_delta = self.panel_time - now
            except ValueError:
                _logger.debug(f"Failed to parse panel time: {panel_time_str}")
                self.panel_time = now + self._panel_time_delta

        try:
            now = datetime.now(timezone.utc)
            if self._last_update is None or now > self._last_update + timedelta(seconds=MIN_UPDATE_INTERVAL):
                self._last_update = now
                await self.hass.async_add_executor_job(fetch_data)
                parse_panel_time()
            return self.status, self.panel_data #, self.sensor_data
        except Exception as e:
            _logger.error(f"Exception occurred while fetching HKC data: {e}")
            _logger.error(traceback.format_exc())
            raise UpdateFailed(f"Failed to update: {e}")

class HKCSensorCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, hkc_alarm: HKCAlarm, alarm_coordinator: DataUpdateCoordinator, update_interval) -> None:
        super().__init__(
            hass,
            _logger,
            config_entry=config_entry,
            name="hkc_sensor_data",
            update_interval=timedelta(seconds=update_interval),
        )
        self._last_update = None
        self._hkc_alarm = hkc_alarm
        self._alarm_coordinator = alarm_coordinator
        self.sensor_data = None

    async def _async_update_data(self):
        def fetch_data():
            self.sensor_data = self._hkc_alarm.get_all_inputs()

        try:
            await self._alarm_coordinator.async_refresh()
            now = datetime.now(timezone.utc)
            if self._last_update is None or now > self._last_update + timedelta(seconds=MIN_UPDATE_INTERVAL):
                self._last_update = now
                await self.hass.async_add_executor_job(fetch_data)
            return self.sensor_data
        except Exception as e:
            _logger.error(f"Exception occurred while fetching HKC sensor data: {e}")
            _logger.error(traceback.format_exc())
            raise UpdateFailed(f"Failed to update: {e}")


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry):
    if entry.version > 3:
        # This means the user has downgraded from a future version
        return False

    new_data = {**entry.data}
    new_options = {**entry.options}
    if entry.version < 3:
        # Move update_interval to options so it can be changed on the fly
        if CONF_UPDATE_INTERVAL not in new_options:
            new_options[CONF_UPDATE_INTERVAL] = DEFAULT_UPDATE_INTERVAL
        if (update_interval := new_data.get(CONF_UPDATE_INTERVAL)) is not None:
            new_options[CONF_UPDATE_INTERVAL] = update_interval
            del new_data[CONF_UPDATE_INTERVAL]

    hass.config_entries.async_update_entry(
        entry,
        data=new_data,
        options=new_options,
        version=HKCAlarmConfigFlow.VERSION,
        minor_version=HKCAlarmConfigFlow.MINOR_VERSION
    )
    _logger.debug(
        "Migration to configuration version %s.%s successful",
        entry.version,
        entry.minor_version,
    )
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    panel_id = entry.data["panel_id"]
    panel_password = entry.data["panel_password"]
    user_code = entry.data["user_code"]

    hkc_alarm = await hass.async_add_executor_job(
        HKCAlarm, panel_id, panel_password, user_code
    )

    update_interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    alarm_coordinator = HKCAlarmCoordinator(hass, entry, hkc_alarm, update_interval)
    sensor_coordinator = HKCSensorCoordinator(
        hass, entry, hkc_alarm, alarm_coordinator, update_interval
    )
    await alarm_coordinator.async_config_entry_first_refresh()
    await sensor_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "hkc_alarm": hkc_alarm,
        "update_interval": update_interval,
        "alarm_coordinator": alarm_coordinator,
        "sensor_coordinator": sensor_coordinator,
    }

    @callback
    async def update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
        update_interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        hass.data[DOMAIN][entry.entry_id]["update_interval"] = update_interval
        alarm_coordinator.update_interval = timedelta(seconds=update_interval)
        sensor_coordinator.update_interval = timedelta(seconds=update_interval)
        await sensor_coordinator.async_refresh()  # will refresh alarm_coordinator

    entry.async_on_unload(entry.add_update_listener(update_options))

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
