from datetime import datetime, timedelta
import logging
import pytz
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

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

        self._attr_has_entity_name = True
        self._attr_name = input_data["description"]

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

    def _get_sensor_state(self) -> str:
        """Determine the state of the sensor."""

        # Check for the default timestamp
        if self._input_data["timestamp"] == "0001-01-01T00:00:00":
            _logger.debug(
                f"Sensor {self.name} state determined as 'Unused' due to default timestamp."
            )
            return "Unused"

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

        time_difference = sensor_timestamp - self._alarm_coordinator.panel_time

        # Handle cases where the timestamp is very old or invalid
        if time_difference > timedelta(days=365):
            _logger.debug(
                f"Sensor {self.name} has an old timestamp: {self._input_data['timestamp']}. Setting state to 'Closed'."
            )
            return "Closed"  # Or return "Unknown" if you prefer

        # Check if the time difference is within 60 seconds (maximum panel time resolution) to determine 'Open' state
        if abs(time_difference) < timedelta(seconds=60):
            _logger.debug(
                f"Sensor {self.name} state determined as 'Open' due to timestamp within 60 seconds of panel time."
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
            self._attr_native_value = self._get_sensor_state()
        else:
            _logger.warning(
                f"No matching sensor data found for inputId {self._input_data.get('inputId')}"
            )

        self.async_write_ha_state()  # Update the state with the latest data


async def async_setup_entry(hass, entry, async_add_entities):
    hkc_alarm = hass.data[DOMAIN][entry.entry_id]["hkc_alarm"]
    alarm_coordinator = hass.data[DOMAIN][entry.entry_id]["alarm_coordinator"]
    sensor_coordinator = hass.data[DOMAIN][entry.entry_id]["sensor_coordinator"]

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
