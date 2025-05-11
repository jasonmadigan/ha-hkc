import logging
from pyhkc.hkc_api import HKCAlarm
import pytz
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from datetime import datetime, timezone, timedelta
from homeassistant.util import Throttle
from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL, CONF_UPDATE_INTERVAL

_logger = logging.getLogger(__name__)


class HKCSensor(CoordinatorEntity, SensorEntity):

    def __init__(self, hkc_alarm, input_data, alarm_coordinator, sensor_coordinator):
        super().__init__(
            sensor_coordinator
        )  # Ensure the coordinator is properly initialized
        self._hkc_alarm = hkc_alarm
        self._input_data = input_data
        self._alarm_coordinator = alarm_coordinator
        self._sensor_coordinator = sensor_coordinator

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the alarm sensors"""
        if self._alarm_coordinator.panel_time_offset is None:
            return None

        attributes = {"Panel Offset": round(self._alarm_coordinator.panel_time_offset)}
        return attributes

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return str(self._hkc_alarm.panel_id) + str(self._input_data["inputId"])

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
        """Determine the state of the sensor."""

        # Check for the default timestamp
        if self._input_data["timestamp"] == "0001-01-01T00:00:00":
            _logger.debug(
                f"Sensor {self.name} state determined as 'Unused' due to default timestamp."
            )
            return "Unused"

        # Parse panel time
        panel_time_str = self._alarm_coordinator.panel_data.get("display", "")

        try:
            panel_time = datetime.strptime(panel_time_str, "%a %d %b %H:%M")
        except ValueError:
            _logger.debug(
                f"Failed to parse panel time: {panel_time_str} for sensor {self.name}. Falling back to previously known panel offset."
            )
            # Fallback to previously known panel offset
            panel_time_offset = self._alarm_coordinator.panel_time_offset

            if panel_time_offset is None:
                # No previously known panel offset, we're stuck
                return "Unknown"

            # Round the offset value
            panel_offset_in_minutes = round(panel_time_offset)

            # Calculate new panel_time
            current_time = datetime.now()
            panel_time = current_time - timedelta(minutes=panel_offset_in_minutes)

            # Convert panel_time back to string format
            panel_time_str = panel_time.strftime("%a %d %b %H:%M")

        # Ensure Panel Time is in UTC
        current_year = datetime.utcnow().year
        panel_time = panel_time.replace(year=current_year, tzinfo=pytz.UTC)

        # Parse sensor timestamp
        try:
            sensor_timestamp = datetime.strptime(
                self._input_data["timestamp"], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(
                tzinfo=pytz.UTC
            )  # Ensure sensor_timestamp is treated as UTC
        except ValueError:
            try:
                sensor_timestamp = datetime.strptime(
                    self._input_data["timestamp"], "%Y-%m-%dT%H:%M:%S"
                ).replace(
                    tzinfo=pytz.UTC
                )  # Ensure sensor_timestamp is treated as UTC
            except ValueError:
                _logger.debug(
                    f"Failed to parse timestamp: {self._input_data['timestamp']} for sensor {self.name}. Setting state to 'Unknown'."
                )
                return "Unknown"  # Return an unknown state if timestamp parsing fails

        time_difference = panel_time - sensor_timestamp

        # Get panel offset.
        current_time = datetime.now(pytz.UTC)
        time_difference = current_time - panel_time

        # Calculate the difference in minutes
        minutes_difference = time_difference.total_seconds() / 60

        self._alarm_coordinator.panel_time_offset = minutes_difference

        # Handle cases where the timestamp is very old or invalid
        if time_difference > timedelta(days=365):
            _logger.debug(
                f"Sensor {self.name} has an old timestamp: {self._input_data['timestamp']}. Setting state to 'Closed'."
            )
            return "Closed"  # Or return "Unknown" if you prefer

        # Check if the time difference is within 60 seconds (maximum panel time resolution) to determine 'Open' state
        if abs(time_difference) < timedelta(seconds=60):
            _logger.debug(
                f"Sensor {self.name} state determined as 'Open' due to timestamp within 30 seconds of panel time."
            )
            return "Open"
        elif self._input_data["inputState"] == 1:
            _logger.debug(
                f"Sensor {self.name} state determined as 'Open' due to inputState being 1."
            )
            return "Open"
        elif self._input_data["inputState"] == 2:
            _logger.debug(
                f"Sensor {self.name} state determined as 'Tamper' due to inputState being 2."
            )
            return "Tamper"
        elif self._input_data["inputState"] == 5:
            _logger.debug(
                f"Sensor {self.name} state determined as 'Inhibited' due to inputState being 5."
            )
            return "Inhibited"
        else:
            _logger.debug(f"Sensor {self.name} state determined as 'Closed'.")
            return "Closed"

    @property
    def name(self):
        return self._input_data["description"]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Search for the matching sensor data based on inputId
        matching_sensor_data = next(
            (
                sensor_data
                for sensor_data in self._sensor_coordinator.sensor_data
                if sensor_data.get("inputId") == self._input_data.get("inputId")
            ),
            None,  # Default to None if no matching sensor data is found
        )

        if matching_sensor_data is not None:
            # Update self._input_data with the matching sensor data
            self._input_data = matching_sensor_data
        else:
            _logger.warning(
                f"No matching sensor data found for inputId {self._input_data.get('inputId')}"
            )

        self.async_write_ha_state()  # Update the state with the latest data


class HKCSensorCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        hkc_alarm: HKCAlarm,
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
        self._last_update = datetime.min
        self._hkc_alarm = hkc_alarm
        self._alarm_coordinator = alarm_coordinator
        self.sensor_data = None

    async def _async_update_data(self):
        @Throttle(timedelta(seconds=30))
        def fetch_data():
            _logger.warning("hkc_sensor_data fetch")
            self.sensor_data = self._hkc_alarm.get_all_inputs()

        try:
            await self._alarm_coordinator.async_refresh()
            now = datetime.now(timezone.utc)
            if now > self._last_update + timedelta(seconds=30):
                self._last_update = now
                await self.hass.async_add_executor_job(fetch_data)
            return self.sensor_data
        except Exception as e:
            _logger.error(f"Exception occurred while fetching HKC data: {e}")
            raise UpdateFailed(f"Failed to update: {e}")


async def async_setup_entry(hass, entry, async_add_entities):
    hkc_alarm = hass.data[DOMAIN][entry.entry_id]["hkc_alarm"]
    update_interval = entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    alarm_coordinator = hass.data[DOMAIN][entry.entry_id]["alarm_coordinator"]
    sensor_coordinator = HKCSensorCoordinator(
        hass, entry, hkc_alarm, alarm_coordinator, update_interval
    )
    await sensor_coordinator.async_config_entry_first_refresh()

    all_inputs = sensor_coordinator.data
    # Filter out the inputs with empty description
    filtered_inputs = [
        input_data for input_data in all_inputs if input_data["description"]
    ]
    async_add_entities(
        [
            HKCSensor(hkc_alarm, input_data, alarm_coordinator, sensor_coordinator)
            for input_data in filtered_inputs
        ],
        True,
    )
