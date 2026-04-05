from unittest.mock import patch

import pytest
from homeassistant.components.alarm_control_panel import AlarmControlPanelState, CodeFormat
from homeassistant.exceptions import ServiceValidationError

from custom_components.hkc_alarm.alarm_control_panel import HKCAlarmControlPanel
from custom_components.hkc_alarm.const import DOMAIN
from .mock_common import get_mock_alarm_coordinator, get_mock_hass, get_mock_hkc_alarm


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


def build_view(user_code="1234", label="HKC Alarm System", multi_view=False, block_numbers=None):
    return {
        "key": "default" if not multi_view else f"user_{user_code}",
        "user_code": user_code,
        "allowed_user_codes": [user_code],
        "block_numbers": block_numbers or [],
        "label": label,
        "multi_view": multi_view,
    }


@pytest.mark.asyncio
async def test_hkc_alarm_control_panel_state():
    with patch.object(HKCAlarmControlPanel, "async_write_ha_state", return_value=None):
        alarm_control_panel = HKCAlarmControlPanel(
            get_mock_hkc_alarm(),
            build_view(),
            mock_alarm_coordinator := get_mock_alarm_coordinator(),
            False,
        )
        alarm_control_panel.hass = get_mock_hass()
        mock_alarm_coordinator.status = mock_panel_status_disarmed
        mock_alarm_coordinator.status_by_user = {"1234": mock_panel_status_disarmed}
        alarm_control_panel._handle_coordinator_update()

        assert alarm_control_panel.alarm_state == AlarmControlPanelState.DISARMED


@pytest.mark.asyncio
async def test_device_info():
    alarm_control_panel = HKCAlarmControlPanel(
        get_mock_hkc_alarm(), build_view(), get_mock_alarm_coordinator(), False
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
        get_mock_hkc_alarm(), build_view(), get_mock_alarm_coordinator(), False
    )
    assert alarm_control_panel.name is None


@pytest.mark.asyncio
async def test_should_poll():
    alarm_control_panel = HKCAlarmControlPanel(
        get_mock_hkc_alarm(), build_view(), get_mock_alarm_coordinator(), False
    )
    assert alarm_control_panel.should_poll is False


@pytest.mark.asyncio
async def test_async_update():
    alarm_control_panel = HKCAlarmControlPanel(
        get_mock_hkc_alarm(),
        build_view(),
        mock_alarm_coordinator := get_mock_alarm_coordinator(),
        False,
    )
    await alarm_control_panel.async_update()
    mock_alarm_coordinator.async_request_refresh.assert_called()


@pytest.mark.asyncio
async def test_single_user_mode_does_not_require_pin():
    alarm_control_panel = HKCAlarmControlPanel(
        get_mock_hkc_alarm(),
        build_view(),
        get_mock_alarm_coordinator(),
        False,
    )

    assert alarm_control_panel.code_arm_required is False
    assert alarm_control_panel.code_format is None


@pytest.mark.asyncio
async def test_require_pin_option_enables_keypad():
    alarm_control_panel = HKCAlarmControlPanel(
        get_mock_hkc_alarm(),
        build_view(),
        get_mock_alarm_coordinator(),
        True,
    )

    assert alarm_control_panel.code_arm_required is True
    assert alarm_control_panel.code_format == CodeFormat.NUMBER


@pytest.mark.asyncio
async def test_multi_view_alarm_uses_block_specific_unique_id():
    alarm_control_panel = HKCAlarmControlPanel(
        get_mock_hkc_alarm(),
        build_view(user_code="5678", label="Guest Suite", multi_view=True, block_numbers=[2]),
        get_mock_alarm_coordinator(),
        False,
    )

    assert alarm_control_panel.unique_id == "hkc_alarm_instancepanel_user_5678"
    assert alarm_control_panel.name == "Guest Suite"


@pytest.mark.asyncio
async def test_arm_command_uses_default_view_user_without_pin():
    hkc_alarm = get_mock_hkc_alarm()
    alarm_control_panel = HKCAlarmControlPanel(
        hkc_alarm,
        build_view(user_code="5678", label="Guest Suite", multi_view=True, block_numbers=[2]),
        mock_alarm_coordinator := get_mock_alarm_coordinator(),
        False,
    )
    alarm_control_panel.hass = get_mock_hass()

    await alarm_control_panel.async_alarm_arm_home()

    assert hkc_alarm.command_calls[-1] == ("arm_partset_a", "5678", 1)
    mock_alarm_coordinator.async_force_refresh.assert_called()


@pytest.mark.asyncio
async def test_invalid_entered_user_pin_is_rejected():
    alarm_control_panel = HKCAlarmControlPanel(
        get_mock_hkc_alarm(),
        build_view(),
        get_mock_alarm_coordinator(),
        True,
    )
    alarm_control_panel.hass = get_mock_hass()

    with pytest.raises(ServiceValidationError):
        await alarm_control_panel.async_alarm_arm_home("9999")


@pytest.mark.asyncio
async def test_missing_user_pin_is_rejected_when_required():
    alarm_control_panel = HKCAlarmControlPanel(
        get_mock_hkc_alarm(),
        build_view(),
        get_mock_alarm_coordinator(),
        True,
    )
    alarm_control_panel.hass = get_mock_hass()

    with pytest.raises(ServiceValidationError):
        await alarm_control_panel.async_alarm_disarm()


@pytest.mark.asyncio
async def test_user_pin_with_undefined_prefix_is_normalized():
    hkc_alarm = get_mock_hkc_alarm()
    alarm_control_panel = HKCAlarmControlPanel(
        hkc_alarm,
        build_view(),
        mock_alarm_coordinator := get_mock_alarm_coordinator(),
        True,
    )
    alarm_control_panel.hass = get_mock_hass()

    await alarm_control_panel.async_alarm_disarm("undefined1234")

    assert hkc_alarm.command_calls[-1] == ("disarm", "1234", None)
    mock_alarm_coordinator.async_force_refresh.assert_called()


@pytest.mark.asyncio
async def test_user_pin_with_only_undefined_prefix_is_rejected():
    alarm_control_panel = HKCAlarmControlPanel(
        get_mock_hkc_alarm(),
        build_view(),
        get_mock_alarm_coordinator(),
        True,
    )
    alarm_control_panel.hass = get_mock_hass()

    with pytest.raises(ServiceValidationError):
        await alarm_control_panel.async_alarm_disarm("undefined")
