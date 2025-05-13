from pyhkc.hkc_api import HKCAlarm
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL, CONF_UPDATE_INTERVAL

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    panel_id = entry.data["panel_id"]
    panel_password = entry.data["panel_password"]
    user_code = entry.data["user_code"]

    hkc_alarm = await hass.async_add_executor_job(
        HKCAlarm, panel_id, panel_password, user_code
    )

    update_interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    scan_interval = timedelta(seconds=update_interval)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "hkc_alarm": hkc_alarm,
        "scan_interval": scan_interval,
    }

    @callback
    async def update_options(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        update_interval = config_entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        hass.data[DOMAIN][config_entry.entry_id]["scan_interval"] = timedelta(seconds=update_interval)

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
