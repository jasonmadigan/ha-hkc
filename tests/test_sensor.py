from unittest.mock import patch
import pytest
from custom_components.hkc_alarm.sensor import HKCSensor
from custom_components.hkc_alarm.const import DOMAIN
from .mock_common import (
    get_mock_hkc_alarm,
    get_mock_alarm_coordinator,
    get_mock_sensor_coordinator,
    get_mock_hass,
)

# Mock data for HKCSensor to process
mock_sensor_data = {
    "inputId": "1",
    "description": "Front Door",
    "timestamp": "2023-10-25T08:00:00Z",
    "inputState": 1,
}

# Mock tampered sensor data for HKCSensor to process
mock_tampered_sensor_data = {
    "inputId": "2",
    "description": "Front Door",
    "timestamp": "2024-09-02T12:00:00Z",
    "inputState": 2,
}


@pytest.mark.asyncio
async def test_hkc_sensor_state():
    with patch.object(HKCSensor, "async_write_ha_state", return_value=None):
        sensor = HKCSensor(
            "hkc_alarm_instance",
            mock_sensor_data,
            get_mock_alarm_coordinator(),
            mock_sensor_coordinator := get_mock_sensor_coordinator(),
        )
        sensor.hass = get_mock_hass()
        mock_sensor_coordinator.sensor_data = [mock_sensor_data]
        sensor._handle_coordinator_update()

        print(f"Mock Sensor Data: {mock_sensor_data}")  # Print the mock data
        print(f"Sensor State: {sensor.state}")  # Print the actual state

        assert (
            sensor.state == "Open"
        )  # as per your logic, inputState being 1 should result in state "Open"


@pytest.mark.asyncio
async def test_hkc_sensor_tampered_state():
    with patch.object(HKCSensor, "async_write_ha_state", return_value=None):
        sensor = HKCSensor(
            "hkc_alarm_instance",
            mock_tampered_sensor_data,
            get_mock_alarm_coordinator(),
            mock_sensor_coordinator := get_mock_sensor_coordinator(),
        )
        sensor.hass = get_mock_hass()
        mock_sensor_coordinator.sensor_data = [mock_tampered_sensor_data]
        sensor._handle_coordinator_update()

        print(f"Mock Sensor Data: {mock_sensor_data}")
        print(f"Sensor State: {sensor.state}")

        assert (
            sensor.state == "Tamper"
        )  # as per your logic, inputState being 2 should result in state "Tamper"


@pytest.mark.asyncio
async def test_hkc_sensor_invalid_timestamp():
    with patch.object(HKCSensor, "async_write_ha_state", return_value=None):
        sensor = HKCSensor(
            "hkc_alarm_instance",
            mock_sensor_data,
            get_mock_alarm_coordinator(),
            mock_sensor_coordinator := get_mock_sensor_coordinator(),
        )
        sensor.hass = get_mock_hass()
        mock_sensor_coordinator.sensor_data = [
            {
                **mock_sensor_data,
                "timestamp": "invalid_timestamp",
            }
        ]
        sensor._handle_coordinator_update()
        assert (
            sensor.state == "Unknown"
        )  # as per your logic, an invalid timestamp should result in state "Unknown"


@pytest.mark.asyncio
async def test_device_info():
    sensor = HKCSensor(
        get_mock_hkc_alarm(),
        mock_sensor_data,
        get_mock_alarm_coordinator(),
        get_mock_sensor_coordinator(),
    )
    expected_device_info = {
        "identifiers": {(DOMAIN, "hkc_alarm_instance")},
        "name": "HKC Alarm System",
        "manufacturer": "HKC",
        "model": "HKC Alarm",
        "sw_version": "1.0.0",
    }
    assert sensor.device_info == expected_device_info


@pytest.mark.asyncio
async def test_name():
    sensor = HKCSensor(
        "hkc_alarm_instance",
        mock_sensor_data,
        get_mock_alarm_coordinator(),
        get_mock_sensor_coordinator(),
    )
    assert sensor.name == "Front Door"  # Assuming description is 'Front Door'


@pytest.mark.asyncio
async def test_should_poll():
    sensor = HKCSensor(
        "hkc_alarm_instance",
        mock_sensor_data,
        get_mock_alarm_coordinator(),
        get_mock_sensor_coordinator(),
    )
    assert sensor.should_poll is False


@pytest.mark.asyncio
async def test_handle_sensor_coordinator_update():
    with patch.object(HKCSensor, "async_write_ha_state", return_value=None):
        sensor = HKCSensor(
            "hkc_alarm_instance",
            mock_sensor_data,
            get_mock_alarm_coordinator(),
            mock_sensor_coordinator := get_mock_sensor_coordinator(),
        )
        sensor.hass = get_mock_hass()
        sensor.entity_id = "sensor.front_door"  # Set the entity_id manually
        new_data = {
            "inputId": "1",
            "description": "Front Door",
            "timestamp": "2023-10-26T08:00:00Z",
            "inputState": 0,
        }
        mock_sensor_coordinator.sensor_data = [new_data]
        sensor._handle_coordinator_update()
        assert sensor._input_data == new_data  # Check that _input_data was updated


@pytest.mark.asyncio
async def test_async_update():
    sensor = HKCSensor(
        "hkc_alarm_instance",
        mock_sensor_data,
        get_mock_alarm_coordinator(),
        mock_sensor_coordinator := get_mock_sensor_coordinator(),
    )
    await sensor.async_update()
    mock_sensor_coordinator.async_request_refresh.assert_called()  # Verify that a refresh request was made
