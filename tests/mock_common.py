from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock


class MockAlarmCoordinator:
    async_request_refresh = AsyncMock()
    async_force_refresh = AsyncMock()
    last_update_success = True  # or False, depending on what you want to test
    config_entry = None
    status = {}
    status_by_user = {}
    panel_time = datetime.now(timezone.utc) - timedelta(seconds=120)
    panel_data = {
        "greenLed": 0,
        "redLed": 1,
        "amberLed": 1,
        "cursorOn": False,
        "cursorIndex": 0,
        "display": "Mon 12 May 20:55",
        "blink": "0000000000000100",
    }


class MockSensorCoordinator:
    async_request_refresh = AsyncMock()
    last_update_success = True  # or False, depending on what you want to test
    inputs_by_user = {}


class MockHKCAlarm:
    panel_id = "hkc_alarm_instance"

    def __init__(self):
        self.command_calls = []

    def _command(self, command_name, user_code=None):
        self.command_calls.append((command_name, user_code))
        return {"resultCode": 5}

    def arm_partset_a(self, user_code=None):
        return self._command("arm_partset_a", user_code)

    def arm_partset_b(self, user_code=None):
        return self._command("arm_partset_b", user_code)

    def arm_fullset(self, user_code=None):
        return self._command("arm_fullset", user_code)

    def disarm(self, user_code=None):
        return self._command("disarm", user_code)

    def _arm_or_disarm(self, command=None, block=None, user_code=None):
        command_name = {
            0: "disarm",
            1: "arm_partset_a",
            2: "arm_partset_b",
            3: "arm_fullset",
        }[command]
        self.command_calls.append((command_name, user_code, block))
        return {"resultCode": 5}


def get_mock_hkc_alarm():
    return MockHKCAlarm()


def get_mock_alarm_coordinator():
    return MockAlarmCoordinator()


def get_mock_sensor_coordinator():
    return MockSensorCoordinator()


# MagicMock for the hass attribute
def get_mock_hass():
    mock_hass = MagicMock()
    mock_hass.async_add_executor_job = AsyncMock(
        side_effect=lambda func, *args: func(*args)
    )
    mock_hass.bus.async_fire = MagicMock()
    mock_hass.data.get.return_value = {}
    return mock_hass
