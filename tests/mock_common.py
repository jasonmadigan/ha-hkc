from unittest.mock import MagicMock, AsyncMock


class MockAlarmCoordinator:
    async_request_refresh = AsyncMock()
    last_update_success = True  # or False, depending on what you want to test


class MockSensorCoordinator:
    async_request_refresh = AsyncMock()
    last_update_success = True  # or False, depending on what you want to test


class MockHKCAlarm:
    panel_id = "hkc_alarm_instance"


def get_mock_hkc_alarm():
    return MockHKCAlarm()


def get_mock_alarm_coordinator():
    return MockAlarmCoordinator()


def get_mock_sensor_coordinator():
    return MockSensorCoordinator()


# MagicMock for the hass attribute
def get_mock_hass():
    mock_hass = MagicMock()
    # Set up the get method of the data attribute to return an empty dictionary
    mock_hass.data.get.return_value = {}
    return mock_hass
