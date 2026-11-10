import warnings
from datetime import datetime, timezone

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hkc_alarm import HKCAlarmCoordinator
from custom_components.hkc_alarm.const import DOMAIN
from .mock_common import MockHKCAlarm


class PanelClockAlarm(MockHKCAlarm):
    def __init__(self, display):
        super().__init__()
        self.display = display

    def get_system_status(self, user_code=None):
        return {"blocks": []}

    def get_panel(self):
        return {"display": self.display}


def build_coordinator(hass, display):
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    return HKCAlarmCoordinator(hass, entry, PanelClockAlarm(display), ["1234"], 60)


async def refresh(coordinator):
    with warnings.catch_warnings():
        # python 3.13+ deprecates strptime dates without a year
        warnings.filterwarnings(
            "error", message=".*without a year", category=DeprecationWarning
        )
        await coordinator.async_force_refresh()
    assert coordinator.last_update_success


async def test_panel_time_uses_current_year(hass, freezer):
    freezer.move_to("2026-11-10 17:48:30+00:00")
    coordinator = build_coordinator(hass, "Tue 10 Nov 17:48")

    await refresh(coordinator)

    assert coordinator.panel_time == datetime(2026, 11, 10, 17, 48, tzinfo=timezone.utc)


async def test_panel_time_parses_leap_day(hass, freezer):
    freezer.move_to("2028-02-29 12:00:30+00:00")
    coordinator = build_coordinator(hass, "Tue 29 Feb 12:00")

    await refresh(coordinator)

    assert coordinator.panel_time == datetime(2028, 2, 29, 12, 0, tzinfo=timezone.utc)


async def test_panel_time_keeps_previous_year_just_after_new_year(hass, freezer):
    freezer.move_to("2027-01-01 00:00:30+00:00")
    coordinator = build_coordinator(hass, "Thu 31 Dec 23:59")

    await refresh(coordinator)

    assert coordinator.panel_time == datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc)


async def test_unreadable_display_keeps_last_panel_offset(hass, freezer):
    freezer.move_to("2026-11-10 17:48:30+00:00")
    coordinator = build_coordinator(hass, "Tue 10 Nov 17:48")
    await refresh(coordinator)

    coordinator._hkc_alarm.display = "Mains Fault"
    freezer.move_to("2026-11-10 17:50:30+00:00")
    await refresh(coordinator)

    assert coordinator.panel_time == datetime(2026, 11, 10, 17, 50, tzinfo=timezone.utc)
