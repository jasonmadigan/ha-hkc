from datetime import datetime, timedelta, timezone
import pytest
from custom_components.hkc_alarm.alarm_control_panel import (
    HKCAlarmControlPanel,
    AlarmControlPanelState,
)
from custom_components.hkc_alarm.sensor import HKCSensor
from custom_components.hkc_alarm.const import DOMAIN
from unittest.mock import AsyncMock, patch, MagicMock


# MagicMock for the hass attribute
mock_hass = MagicMock()
# Set up the get method of the data attribute to return an empty dictionary
mock_hass.data.get.return_value = {}

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

mock_panel_time = datetime.now(timezone.utc) - timedelta(seconds=120)
mock_panel_data = {
    "greenLed": 0,
    "redLed": 1,
    "amberLed": 1,
    "cursorOn": False,
    "cursorIndex": 0,
    "display": "Mon 12 May 20:55",
    "blink": "0000000000000100",
}
mock_panel_status_disarmed = {
    "blocks": [
        {
            "armState": 0,
            "isEnabled": True,
            "inAlarm": False,
            "inFault": False,
            "userAllowed": True,
            "inhibit": False,
        }
    ],
}


class MockAlarmCoordinator:
    async_request_refresh = AsyncMock()
    last_update_success = True  # or False, depending on what you want to test


class MockSensorCoordinator:
    async_request_refresh = AsyncMock()
    last_update_success = True  # or False, depending on what you want to test


class MockHKCAlarm:
    panel_id = "hkc_alarm_instance"


@pytest.mark.asyncio
async def test_hkc_alarm_control_panel_state():
    with patch.object(HKCAlarmControlPanel, "async_write_ha_state", return_value=None):
        mock_hkc_alarm = MockHKCAlarm()
        mock_alarm_coordinator = MockAlarmCoordinator()
        mock_alarm_control_panel = HKCAlarmControlPanel(
            mock_hkc_alarm, {}, mock_alarm_coordinator
        )
        mock_alarm_control_panel.hass = mock_hass
        mock_alarm_coordinator.status = mock_panel_status_disarmed
        mock_alarm_coordinator.panel_data = mock_panel_data
        mock_alarm_coordinator.panel_time = mock_panel_time
        mock_alarm_control_panel._handle_coordinator_update()

        print(f"Mock Panel Data: {mock_panel_data}")  # Print the mock data
        print(
            f"Sensor State: {mock_alarm_control_panel.alarm_state}"
        )  # Print the actual state

        assert mock_alarm_control_panel.alarm_state == AlarmControlPanelState.DISARMED


@pytest.mark.asyncio
async def test_hkc_sensor_state():
    with patch.object(HKCSensor, "async_write_ha_state", return_value=None):
        mock_alarm_coordinator = MockAlarmCoordinator()
        mock_sensor_coordinator = MockSensorCoordinator()
        sensor = HKCSensor(
            "hkc_alarm_instance",
            mock_sensor_data,
            mock_alarm_coordinator,
            mock_sensor_coordinator,
        )
        sensor.hass = mock_hass
        mock_sensor_coordinator.sensor_data = [mock_sensor_data]
        mock_alarm_coordinator.panel_time = mock_panel_time
        sensor._handle_coordinator_update()

        print(f"Mock Sensor Data: {mock_sensor_data}")  # Print the mock data
        print(f"Sensor State: {sensor.state}")  # Print the actual state

        assert (
            sensor.state == "Open"
        )  # as per your logic, inputState being 1 should result in state "Open"


@pytest.mark.asyncio
async def test_hkc_sensor_tampered_state():
    with patch.object(HKCSensor, "async_write_ha_state", return_value=None):
        mock_alarm_coordinator = MockAlarmCoordinator()
        mock_sensor_coordinator = MockSensorCoordinator()
        sensor = HKCSensor(
            "hkc_alarm_instance",
            mock_tampered_sensor_data,
            mock_alarm_coordinator,
            mock_sensor_coordinator,
        )
        sensor.hass = mock_hass
        mock_sensor_coordinator.sensor_data = [mock_tampered_sensor_data]
        mock_alarm_coordinator.panel_time = mock_panel_time
        sensor._handle_coordinator_update()

        print(f"Mock Sensor Data: {mock_sensor_data}")
        print(f"Sensor State: {sensor.state}")

        assert (
            sensor.state == "Tamper"
        )  # as per your logic, inputState being 2 should result in state "Tamper"


@pytest.mark.asyncio
async def test_hkc_sensor_invalid_timestamp():
    with patch.object(HKCSensor, "async_write_ha_state", return_value=None):
        mock_alarm_coordinator = MockAlarmCoordinator()
        mock_sensor_coordinator = MockSensorCoordinator()
        sensor = HKCSensor(
            "hkc_alarm_instance",
            mock_sensor_data,
            mock_alarm_coordinator,
            mock_sensor_coordinator,
        )
        sensor.hass = mock_hass
        mock_sensor_coordinator.sensor_data = [
            {
                **mock_sensor_data,
                "timestamp": "invalid_timestamp",
            }
        ]
        mock_alarm_coordinator.panel_time = mock_panel_time
        sensor._handle_coordinator_update()
        assert (
            sensor.state == "Unknown"
        )  # as per your logic, an invalid timestamp should result in state "Unknown"


@pytest.mark.asyncio
async def test_device_info():
    mock_hkc_alarm = MockHKCAlarm()
    mock_alarm_coordinator = MockAlarmCoordinator()
    mock_sensor_coordinator = MockSensorCoordinator()
    sensor = HKCSensor(
        mock_hkc_alarm,
        mock_sensor_data,
        mock_alarm_coordinator,
        mock_sensor_coordinator,
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
    mock_alarm_coordinator = MockAlarmCoordinator()
    mock_sensor_coordinator = MockSensorCoordinator()
    sensor = HKCSensor(
        "hkc_alarm_instance",
        mock_sensor_data,
        mock_alarm_coordinator,
        mock_sensor_coordinator,
    )
    assert sensor.name == "Front Door"  # Assuming description is 'Front Door'


@pytest.mark.asyncio
async def test_should_poll():
    mock_alarm_coordinator = MockAlarmCoordinator()
    mock_sensor_coordinator = MockSensorCoordinator()
    sensor = HKCSensor(
        "hkc_alarm_instance",
        mock_sensor_data,
        mock_alarm_coordinator,
        mock_sensor_coordinator,
    )
    assert sensor.should_poll is False


@pytest.mark.asyncio
async def test_handle_sensor_coordinator_update():
    with patch.object(HKCSensor, "async_write_ha_state", return_value=None):
        mock_alarm_coordinator = MockAlarmCoordinator()
        mock_sensor_coordinator = MockSensorCoordinator()
        sensor = HKCSensor(
            "hkc_alarm_instance",
            mock_sensor_data,
            mock_alarm_coordinator,
            mock_sensor_coordinator,
        )
        sensor.hass = mock_hass
        sensor.entity_id = "sensor.front_door"  # Set the entity_id manually
        new_data = {
            "inputId": "1",
            "description": "Front Door",
            "timestamp": "2023-10-26T08:00:00Z",
            "inputState": 0,
        }
        mock_sensor_coordinator.sensor_data = [new_data]
        mock_alarm_coordinator.panel_time = mock_panel_time
        sensor._handle_coordinator_update()
        assert sensor._input_data == new_data  # Check that _input_data was updated


@pytest.mark.asyncio
async def test_async_update():
    mock_alarm_coordinator = MockAlarmCoordinator()
    mock_sensor_coordinator = MockSensorCoordinator()
    sensor = HKCSensor(
        "hkc_alarm_instance",
        mock_sensor_data,
        mock_alarm_coordinator,
        mock_sensor_coordinator,
    )
    await sensor.async_update()
    mock_sensor_coordinator.async_request_refresh.assert_called()  # Verify that a refresh request was made
