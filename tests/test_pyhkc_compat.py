from custom_components.hkc_alarm.pyhkc_compat import build_hkc_alarm, get_remote_keypad


class FakeHKCAlarm:
    def __init__(
        self,
        panel_id,
        panel_password,
        user_code,
        user_codes=None,
        request_timeout=None,
    ):
        self.panel_id = panel_id
        self.panel_password = panel_password
        self.user_code = user_code
        self.user_codes = user_codes
        self.request_timeout = request_timeout

    def get_remote_keypad(self):
        return {"display": "Ready"}


class LegacyHKCAlarm:
    def __init__(self, panel_id, panel_password, user_code):
        self.panel_id = panel_id
        self.panel_password = panel_password
        self.user_code = user_code

    def get_panel(self):
        return {"display": "Legacy"}


def test_build_hkc_alarm_passes_supported_new_client_kwargs(monkeypatch):
    monkeypatch.setattr("custom_components.hkc_alarm.pyhkc_compat.HKCAlarm", FakeHKCAlarm)

    alarm = build_hkc_alarm(
        "123456",
        "panel-password",
        "1111",
        ["2222"],
        request_timeout=15,
    )

    assert alarm.user_codes == ["2222"]
    assert alarm.request_timeout == 15


def test_get_remote_keypad_prefers_new_method(monkeypatch):
    monkeypatch.setattr("custom_components.hkc_alarm.pyhkc_compat.HKCAlarm", FakeHKCAlarm)

    alarm = FakeHKCAlarm("123456", "panel-password", "1111")

    assert get_remote_keypad(alarm) == {"display": "Ready"}


def test_get_remote_keypad_falls_back_to_legacy_panel_method():
    alarm = LegacyHKCAlarm("123456", "panel-password", "1111")

    assert get_remote_keypad(alarm) == {"display": "Legacy"}
