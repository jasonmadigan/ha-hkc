from pyhkc.hkc_api import HKCAlarm
from datetime import timedelta
from homeassistant.core import callback
from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL, CONF_UPDATE_INTERVAL

async def async_setup_entry(hass, entry):
    panel_id = entry.data["panel_id"]
    panel_password = entry.data["panel_password"]
    user_code = entry.data["user_code"]

    hkc_alarm = await hass.async_add_executor_job(
        HKCAlarm, panel_id, panel_password, user_code
    )

    # Get update interval from options, or use default
    update_interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    SCAN_INTERVAL = timedelta(seconds=update_interval)

    # Create a dictionary to store both the HKCAlarm instance and SCAN_INTERVAL
    entry_data = {
        "hkc_alarm": hkc_alarm,
        "scan_interval": SCAN_INTERVAL
    }

    # Store the dictionary in hass.data
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry_data

    @callback
    def update_options(entry):
        """Update options."""
        nonlocal entry_data
        update_interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        entry_data["scan_interval"] = timedelta(seconds=update_interval)

    entry.add_update_listener(update_options)

    # Load platforms
    await hass.config_entries.async_forward_entry_setups(
        entry, ["alarm_control_panel", "sensor"]
    )
    return True
