import pytest
from unittest.mock import AsyncMock, patch
from custom_components.hkc_alarm.sensor import HKCSensor
from custom_components.hkc_alarm.const import DOMAIN
from unittest.mock import Mock
from unittest.mock import MagicMock


# Mock data for HKCSensor to process
mock_sensor_data = {
    "inputId": "1",
    "description": "Front Door",
    "timestamp": "2023-10-25T08:00:00Z",
    "inputState": 1,
}


class MockCoordinator:
    async_request_refresh = AsyncMock()
    last_update_success = True  # or False, depending on what you want to test


class MockHKCAlarm:
    panel_id = "hkc_alarm_instance"


@pytest.mark.asyncio
async def test_hkc_sensor_state(hass, aioclient_mock):
    with patch.object(HKCSensor, "_panel_data", {"display": "Thu 26 Oct 10:35"}):
        mock_coordinator = MockCoordinator()  # Create a mock coordinator instance
        sensor = HKCSensor(
            "hkc_alarm_instance", mock_sensor_data, mock_coordinator
        )  # Pass the mock coordinator here
        await sensor.async_update()

        print(f"Mock Sensor Data: {mock_sensor_data}")  # Print the mock data
        print(f"Sensor State: {sensor.state}")  # Print the actual state

        assert (
            sensor.state == "Open"
        )  # as per your logic, inputState being 1 should result in state "Open"


@pytest.mark.asyncio
async def test_hkc_sensor_invalid_timestamp(hass, aioclient_mock):
    with patch(
        "custom_components.hkc_alarm.sensor.HKCSensor.update_panel_data",
        new_callable=AsyncMock,
    ) as mock_update:
        # Include 'display' field in the mocked return value
        mock_update.return_value = {
            **mock_sensor_data,
            "timestamp": "invalid_timestamp",
            "display": "Thu 26 Oct 10:35",
        }

        mock_coordinator = MockCoordinator()  # Create a mock coordinator instance
        sensor = HKCSensor("hkc_alarm_instance", mock_sensor_data, mock_coordinator)
        await sensor.async_update()

        assert (
            sensor.state == "Unknown"
        )  # as per your logic, an invalid timestamp should result in state "Unknown"


@pytest.mark.asyncio
async def test_device_info():
    mock_hkc_alarm = MockHKCAlarm()
    mock_coordinator = MockCoordinator()
    sensor = HKCSensor(mock_hkc_alarm, mock_sensor_data, mock_coordinator)
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
    mock_coordinator = MockCoordinator()
    sensor = HKCSensor("hkc_alarm_instance", mock_sensor_data, mock_coordinator)
    assert sensor.name == "Front Door"  # Assuming description is 'Front Door'


@pytest.mark.asyncio
async def test_should_poll():
    mock_coordinator = MockCoordinator()
    sensor = HKCSensor("hkc_alarm_instance", mock_sensor_data, mock_coordinator)
    assert sensor.should_poll is False


@pytest.mark.asyncio
async def test_handle_coordinator_update():
    mock_coordinator = MockCoordinator()
    sensor = HKCSensor("hkc_alarm_instance", mock_sensor_data, mock_coordinator)

    # Create a MagicMock for the hass attribute
    mock_hass = MagicMock()
    # Set up the get method of the data attribute to return an empty dictionary
    mock_hass.data.get.return_value = {}
    # Assign the mock_hass object to the hass attribute of the sensor
    sensor.hass = mock_hass

    sensor.entity_id = "sensor.front_door"  # Set the entity_id manually
    new_data = {
        "inputId": "1",
        "description": "Front Door",
        "timestamp": "2023-10-26T08:00:00Z",
        "inputState": 0,
    }
    mock_coordinator.data = [new_data]  # Updating the coordinator data
    sensor._handle_coordinator_update()
    assert sensor._input_data == new_data  # Check that _input_data was updated


@pytest.mark.asyncio
async def test_async_update():
    mock_coordinator = MockCoordinator()
    sensor = HKCSensor("hkc_alarm_instance", mock_sensor_data, mock_coordinator)
    await sensor.async_update()
    mock_coordinator.async_request_refresh.assert_called()  # Verify that a refresh request was made
