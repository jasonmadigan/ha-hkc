from unittest.mock import patch

import pytest

from custom_components.hkc_alarm.const import DOMAIN
from custom_components.hkc_alarm.sensor import HKCSensor
from .mock_common import (
    get_mock_alarm_coordinator,
    get_mock_hass,
    get_mock_hkc_alarm,
    get_mock_sensor_coordinator,
)


mock_sensor_data = {
    "inputId": "1",
    "description": "Front Door",
    "timestamp": "2023-10-25T08:00:00Z",
    "inputState": 1,
}

mock_tampered_sensor_data = {
    "inputId": "2",
    "description": "Front Door",
    "timestamp": "2024-09-02T12:00:00Z",
    "inputState": 2,
}


def build_view(user_code="1234", label="HKC Alarm System", multi_view=False):
    return {
        "key": "default" if not multi_view else f"user_{user_code}",
        "user_code": user_code,
        "allowed_user_codes": [user_code],
        "block_numbers": [],
        "label": label,
        "multi_view": multi_view,
    }


@pytest.mark.asyncio
async def test_hkc_sensor_state():
    with patch.object(HKCSensor, "async_write_ha_state", return_value=None):
        sensor = HKCSensor(
            get_mock_hkc_alarm(),
            mock_sensor_data,
            get_mock_alarm_coordinator(),
            mock_sensor_coordinator := get_mock_sensor_coordinator(),
            build_view(),
        )
        sensor.hass = get_mock_hass()
        mock_sensor_coordinator.sensor_data = [mock_sensor_data]
        mock_sensor_coordinator.inputs_by_user = {"1234": [mock_sensor_data]}
        sensor._handle_coordinator_update()

        assert sensor.state == "Open"


@pytest.mark.asyncio
async def test_hkc_sensor_tampered_state():
    with patch.object(HKCSensor, "async_write_ha_state", return_value=None):
        sensor = HKCSensor(
            get_mock_hkc_alarm(),
            mock_tampered_sensor_data,
            get_mock_alarm_coordinator(),
            mock_sensor_coordinator := get_mock_sensor_coordinator(),
            build_view(),
        )
        sensor.hass = get_mock_hass()
        mock_sensor_coordinator.sensor_data = [mock_tampered_sensor_data]
        mock_sensor_coordinator.inputs_by_user = {"1234": [mock_tampered_sensor_data]}
        sensor._handle_coordinator_update()

        assert sensor.state == "Tamper"


@pytest.mark.asyncio
async def test_hkc_sensor_invalid_timestamp():
    with patch.object(HKCSensor, "async_write_ha_state", return_value=None):
        sensor = HKCSensor(
            get_mock_hkc_alarm(),
            mock_sensor_data,
            get_mock_alarm_coordinator(),
            mock_sensor_coordinator := get_mock_sensor_coordinator(),
            build_view(),
        )
        sensor.hass = get_mock_hass()
        invalid_data = {**mock_sensor_data, "timestamp": "invalid_timestamp"}
        mock_sensor_coordinator.sensor_data = [invalid_data]
        mock_sensor_coordinator.inputs_by_user = {"1234": [invalid_data]}
        sensor._handle_coordinator_update()
        assert sensor.state == "Unknown"


@pytest.mark.asyncio
async def test_device_info():
    sensor = HKCSensor(
        get_mock_hkc_alarm(),
        mock_sensor_data,
        get_mock_alarm_coordinator(),
        get_mock_sensor_coordinator(),
        build_view(),
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
        get_mock_hkc_alarm(),
        mock_sensor_data,
        get_mock_alarm_coordinator(),
        get_mock_sensor_coordinator(),
        build_view(),
    )
    assert sensor.name == "Front Door"


@pytest.mark.asyncio
async def test_should_poll():
    sensor = HKCSensor(
        get_mock_hkc_alarm(),
        mock_sensor_data,
        get_mock_alarm_coordinator(),
        get_mock_sensor_coordinator(),
        build_view(),
    )
    assert sensor.should_poll is False


@pytest.mark.asyncio
async def test_handle_sensor_coordinator_update():
    with patch.object(HKCSensor, "async_write_ha_state", return_value=None):
        sensor = HKCSensor(
            get_mock_hkc_alarm(),
            mock_sensor_data,
            get_mock_alarm_coordinator(),
            mock_sensor_coordinator := get_mock_sensor_coordinator(),
            build_view(),
        )
        sensor.hass = get_mock_hass()
        sensor.entity_id = "sensor.front_door"
        new_data = {
            "inputId": "1",
            "description": "Front Door",
            "timestamp": "2023-10-26T08:00:00Z",
            "inputState": 0,
        }
        mock_sensor_coordinator.sensor_data = [new_data]
        mock_sensor_coordinator.inputs_by_user = {"1234": [new_data]}
        sensor._handle_coordinator_update()
        assert sensor._input_data == new_data


@pytest.mark.asyncio
async def test_multi_view_sensor_unique_id_is_namespaced():
    sensor = HKCSensor(
        get_mock_hkc_alarm(),
        mock_sensor_data,
        get_mock_alarm_coordinator(),
        get_mock_sensor_coordinator(),
        build_view(user_code="5678", label="Guest Suite", multi_view=True),
    )
    assert sensor.unique_id == "hkc_alarm_instance_user_5678_1"


@pytest.mark.asyncio
async def test_async_update():
    sensor = HKCSensor(
        get_mock_hkc_alarm(),
        mock_sensor_data,
        get_mock_alarm_coordinator(),
        mock_sensor_coordinator := get_mock_sensor_coordinator(),
        build_view(),
    )
    await sensor.async_update()
    mock_sensor_coordinator.async_request_refresh.assert_called()
