from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from custom_components.hkc_alarm.alarm_control_panel import HKCAlarmControlPanel
from custom_components.hkc_alarm.const import DOMAIN
from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from .mock_common import get_mock_hkc_alarm, get_mock_alarm_coordinator, get_mock_hass


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


@pytest.mark.asyncio
async def test_hkc_alarm_control_panel_state():
    with patch.object(HKCAlarmControlPanel, "async_write_ha_state", return_value=None):
        mock_alarm_coordinator = get_mock_alarm_coordinator()
        alarm_control_panel = HKCAlarmControlPanel(
            get_mock_hkc_alarm(), {}, mock_alarm_coordinator
        )
        alarm_control_panel.hass = get_mock_hass()
        mock_alarm_coordinator.status = mock_panel_status_disarmed
        mock_alarm_coordinator.panel_data = mock_panel_data
        mock_alarm_coordinator.panel_time = mock_panel_time
        alarm_control_panel._handle_coordinator_update()

        print(f"Mock Panel Data: {mock_panel_data}")  # Print the mock data
        print(
            f"Sensor State: {alarm_control_panel.alarm_state}"
        )  # Print the actual state

        assert alarm_control_panel.alarm_state == AlarmControlPanelState.DISARMED


@pytest.mark.asyncio
async def test_device_info():
    alarm_control_panel = HKCAlarmControlPanel(
        get_mock_hkc_alarm(), {}, get_mock_alarm_coordinator()
    )
    expected_device_info = {
        "identifiers": {(DOMAIN, "hkc_alarm_instance")},
        "name": "HKC Alarm System",
        "manufacturer": "HKC",
        "model": "HKC Alarm",
        "sw_version": "1.0.0",
    }
    assert alarm_control_panel.device_info == expected_device_info


@pytest.mark.asyncio
async def test_name():
    alarm_control_panel = HKCAlarmControlPanel(
        get_mock_hkc_alarm(), {}, get_mock_alarm_coordinator()
    )
    assert alarm_control_panel.name == "HKC Alarm System"


@pytest.mark.asyncio
async def test_should_poll():
    alarm_control_panel = HKCAlarmControlPanel(
        get_mock_hkc_alarm(), {}, get_mock_alarm_coordinator()
    )
    assert alarm_control_panel.should_poll is False


@pytest.mark.asyncio
async def test_async_update():
    mock_alarm_coordinator = get_mock_alarm_coordinator()
    alarm_control_panel = HKCAlarmControlPanel(
        get_mock_hkc_alarm(), {}, mock_alarm_coordinator
    )
    await alarm_control_panel.async_update()
    mock_alarm_coordinator.async_request_refresh.assert_called()  # Verify that a refresh request was made
