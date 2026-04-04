from datetime import datetime, timedelta
import logging
import pytz
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_logger = logging.getLogger(__name__)


def _input_identifier(input_data):
    """Return a stable input identifier from HKC payloads."""
    return input_data.get("inputId", input_data.get("input"))


def _dedupe_inputs(inputs):
    """Return inputs de-duplicated by HKC input identifier."""
    deduped = {}
    for input_data in inputs:
        input_id = _input_identifier(input_data)
        if input_id is None:
            continue
        deduped.setdefault(str(input_id), input_data)
    return list(deduped.values())


class HKCSensor(CoordinatorEntity, SensorEntity):

    def __init__(
        self,
        hkc_alarm,
        input_data,
        alarm_coordinator,
        sensor_coordinator,
        view,
    ):
        super().__init__(
            sensor_coordinator
        )  # Ensure the coordinator is properly initialized
        self._hkc_alarm = hkc_alarm
        self._input_data = input_data
        self._alarm_coordinator = alarm_coordinator
        self._sensor_coordinator = sensor_coordinator
        self._view = view

        self._attr_has_entity_name = True
        self._attr_name = input_data["description"]

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        input_id = _input_identifier(self._input_data)
        if not self._view["multi_view"]:
            return str(self._hkc_alarm.panel_id) + str(input_id)
        return f"{self._hkc_alarm.panel_id}_{self._view['key']}_{input_id}"

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
    def extra_state_attributes(self):
        """Return additional HKC input metadata."""
        attributes = {}
        for source_key, target_key in (
            ("inputType", "Input Type"),
            ("actionInhibit", "Action Inhibit"),
            ("cameraId", "Camera ID"),
            ("visibleUserCodes", "Visible User Codes"),
            ("timestamp", "Last Trigger Timestamp"),
        ):
            if source_key in self._input_data:
                attributes[target_key] = self._input_data[source_key]
        return attributes or None

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
        sensor_data_list = self._sensor_coordinator.inputs_by_user.get(
            self._view["user_code"],
            self._sensor_coordinator.sensor_data,
        )
        matching_sensor_data = next(
            (
                sensor_data
                for sensor_data in sensor_data_list
                if _input_identifier(sensor_data) == _input_identifier(self._input_data)
            ),
            None,  # Default to None if no matching sensor data is found
        )

        if matching_sensor_data is not None:
            # Update self._input_data with the matching sensor data
            self._input_data = matching_sensor_data
            self._attr_native_value = self._get_sensor_state()
        else:
            _logger.warning(
                "No matching sensor data found for input %s",
                _input_identifier(self._input_data),
            )

        self.async_write_ha_state()  # Update the state with the latest data


async def async_setup_entry(hass, entry, async_add_entities):
    entry_data = hass.data[DOMAIN][entry.entry_id]
    hkc_alarm = entry_data["hkc_alarm"]
    alarm_coordinator = entry_data["alarm_coordinator"]
    sensor_coordinator = entry_data["sensor_coordinator"]
    entity_map = entry_data.get("entity_map") or {}

    entities = []
    if entity_map.get("blocks"):
        all_inputs = []
        for block in entity_map.get("blocks", []):
            all_inputs.extend(block.get("inputs", []))
        all_inputs.extend(entity_map.get("sharedInputs", []))
        all_inputs.extend(entity_map.get("ambiguousInputs", []))

        sensor_view = {
            "key": "sensors",
            "user_code": entry_data["configured_user_codes"][0],
            "allowed_user_codes": entry_data["configured_user_codes"],
            "block_numbers": [],
            "label": f"{entry_data.get('device_metadata', {}).get('panel_name', 'HKC Alarm System')} Sensors",
            "multi_view": True,
            "kind": "sensors",
        }
        entities.extend(
            [
                HKCSensor(
                    hkc_alarm,
                    input_data,
                    alarm_coordinator,
                    sensor_coordinator,
                    sensor_view,
                )
                for input_data in _dedupe_inputs(all_inputs)
                if input_data.get("description")
            ]
        )
    else:
        for view in entry_data["views"]:
            all_inputs = sensor_coordinator.inputs_by_user.get(
                view["user_code"],
                sensor_coordinator.data,
            )
            filtered_inputs = [
                input_data
                for input_data in all_inputs
                if input_data["description"]
            ]
            entities.extend(
                [
                    HKCSensor(
                        hkc_alarm,
                        input_data,
                        alarm_coordinator,
                        sensor_coordinator,
                        view,
                    )
                    for input_data in filtered_inputs
                ]
            )

    async_add_entities(
        entities,
        True,
    )
