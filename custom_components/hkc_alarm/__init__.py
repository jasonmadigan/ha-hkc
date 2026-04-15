import logging
import traceback
from datetime import datetime, timezone, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pyhkc.hkc_api import HKCAlarm

from .config_flow import HKCAlarmConfigFlow
from .const import (
    CONF_ADDITIONAL_USER_CODES,
    CONF_REQUIRE_USER_PIN,
    CONF_UPDATE_INTERVAL,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_REQUIRE_USER_PIN,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MIN_UPDATE_INTERVAL,
)
from .helpers import normalize_configured_user_codes
from .helpers import build_alarm_views, build_device_metadata
from .pyhkc_compat import (
    build_hkc_alarm,
    get_device_details,
    get_home_assistant_entity_map,
    get_inputs_for_user,
    get_outputs,
    get_remote_keypad,
    get_status_for_user,
    get_temporary_user,
    get_user_access_summary,
)

_logger = logging.getLogger(__name__)

class HKCAlarmCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        hkc_alarm: HKCAlarm,
        configured_user_codes: list[str],
        update_interval,
    ) -> None:
        super().__init__(
            hass,
            _logger,
            config_entry=config_entry,
            name="hkc_alarm_data",
            update_interval=timedelta(seconds=update_interval),
        )
        self._last_update = None
        self._hkc_alarm = hkc_alarm
        self._configured_user_codes = configured_user_codes
        self.panel_time = None
        self._panel_time_delta = timedelta()
        self.status = None
        self.status_by_user: dict[str, dict] = {}
        self.access_summary: dict[int, dict] = {}
        self.panel_data = None

    async def async_force_refresh(self):
        """Force refresh alarm coordinator, ignoring debounce."""
        self._last_update = None
        return await self.async_refresh()

    async def _async_update_data(self):
        def fetch_data():
            self.status_by_user = {
                code: get_status_for_user(self._hkc_alarm, code)
                for code in self._configured_user_codes
            }
            self.status = self.status_by_user[self._configured_user_codes[0]]
            self.access_summary = get_user_access_summary(
                self._hkc_alarm,
                self._configured_user_codes,
                self.status_by_user,
            )
            self.panel_data = get_remote_keypad(self._hkc_alarm)

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
            return self.status_by_user, self.panel_data
        except Exception as e:
            _logger.error(f"Exception occurred while fetching HKC data: {e}")
            _logger.error(traceback.format_exc())
            raise UpdateFailed(f"Failed to update: {e}")

class HKCSensorCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        hkc_alarm: HKCAlarm,
        configured_user_codes: list[str],
        alarm_coordinator: DataUpdateCoordinator,
        update_interval,
    ) -> None:
        super().__init__(
            hass,
            _logger,
            config_entry=config_entry,
            name="hkc_sensor_data",
            update_interval=timedelta(seconds=update_interval),
        )
        self._last_update = None
        self._hkc_alarm = hkc_alarm
        self._configured_user_codes = configured_user_codes
        self._alarm_coordinator = alarm_coordinator
        self.sensor_data = None
        self.inputs_by_user: dict[str, list[dict]] = {}

    async def _async_update_data(self):
        def fetch_data():
            self.inputs_by_user = {
                code: get_inputs_for_user(self._hkc_alarm, code)
                for code in self._configured_user_codes
            }
            self.sensor_data = self.inputs_by_user[self._configured_user_codes[0]]

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
    panel_id = new_data.get("panel_id")
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
        unique_id=panel_id if panel_id else entry.unique_id,
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
    if any(
        existing_entry_id != entry.entry_id
        and existing_data.get("panel_id") == panel_id
        for existing_entry_id, existing_data in hass.data.get(DOMAIN, {}).items()
    ):
        _logger.error(
            "Duplicate HKC Alarm entry detected for panel %s; refusing to set up entry %s",
            panel_id,
            entry.entry_id,
        )
        return False

    panel_password = entry.data["panel_password"]
    user_code = entry.data["user_code"]
    configured_user_codes = normalize_configured_user_codes(
        user_code,
        entry.options.get(CONF_ADDITIONAL_USER_CODES, []),
    )

    hkc_alarm = await hass.async_add_executor_job(
        build_hkc_alarm,
        panel_id,
        panel_password,
        user_code,
        configured_user_codes[1:],
        DEFAULT_REQUEST_TIMEOUT,
    )

    update_interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    require_user_pin = entry.options.get(
        CONF_REQUIRE_USER_PIN, DEFAULT_REQUIRE_USER_PIN
    )
    device_details = await hass.async_add_executor_job(get_device_details, hkc_alarm)
    outputs = await hass.async_add_executor_job(get_outputs, hkc_alarm)
    temporary_user_by_code = await hass.async_add_executor_job(
        lambda: {
            code: get_temporary_user(hkc_alarm, code) for code in configured_user_codes
        }
    )
    device_metadata = build_device_metadata(device_details, outputs)
    initial_statuses = await hass.async_add_executor_job(
        lambda: {
            code: get_status_for_user(hkc_alarm, code) for code in configured_user_codes
        }
    )
    access_summary = await hass.async_add_executor_job(
        get_user_access_summary,
        hkc_alarm,
        configured_user_codes,
        initial_statuses,
    )
    entity_map = await hass.async_add_executor_job(
        get_home_assistant_entity_map,
        hkc_alarm,
        configured_user_codes,
    )
    views = build_alarm_views(
        configured_user_codes,
        access_summary,
        entity_map=entity_map,
        supports_multi_view=hasattr(hkc_alarm, "get_user_access_summary"),
    )

    alarm_coordinator = HKCAlarmCoordinator(
        hass,
        entry,
        hkc_alarm,
        configured_user_codes,
        update_interval,
    )
    sensor_coordinator = HKCSensorCoordinator(
        hass,
        entry,
        hkc_alarm,
        configured_user_codes,
        alarm_coordinator,
        update_interval,
    )
    await alarm_coordinator.async_config_entry_first_refresh()
    await sensor_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "panel_id": panel_id,
        "hkc_alarm": hkc_alarm,
        "update_interval": update_interval,
        "require_user_pin": require_user_pin,
        "configured_user_codes": configured_user_codes,
        "device_details": device_details,
        "device_metadata": device_metadata,
        "outputs": outputs,
        "temporary_user_by_code": temporary_user_by_code,
        "entity_map": entity_map,
        "views": views,
        "alarm_coordinator": alarm_coordinator,
        "sensor_coordinator": sensor_coordinator,
    }

    # clean up orphaned devices from pre-fix multi-view code
    expected_identifiers = {
        (
            DOMAIN,
            f"{hkc_alarm.panel_id}_{v['key']}" if v["multi_view"] else hkc_alarm.panel_id,
        )
        for v in views
    }
    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if not any(ident in expected_identifiers for ident in device.identifiers):
            _logger.info("Removing orphaned device %s (%s)", device.name, device.id)
            device_registry.async_remove_device(device.id)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(
        entry, ["alarm_control_panel", "sensor"]
    )
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor", "alarm_control_panel"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: dr.DeviceEntry,
) -> bool:
    """Allow removal of devices that are no longer active."""
    return True

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
