import pytest

from custom_components.hkc_alarm.helpers import (
    InvalidUserCodeError,
    build_alarm_views,
    normalize_configured_user_codes,
    serialize_user_codes,
)


def test_normalize_configured_user_codes_deduplicates_and_preserves_order():
    assert normalize_configured_user_codes("1234", "5678, 1234, 9999") == [
        "1234",
        "5678",
        "9999",
    ]


def test_normalize_configured_user_codes_rejects_non_numeric_values():
    with pytest.raises(InvalidUserCodeError):
        normalize_configured_user_codes("1234", "ABCD")


def test_serialize_user_codes():
    assert serialize_user_codes(["1234", "5678"]) == "1234, 5678"


def test_build_alarm_views_single_user_stays_backward_compatible():
    views = build_alarm_views(["1234"])

    assert views == [
        {
            "key": "default",
            "user_code": "1234",
            "allowed_user_codes": ["1234"],
            "block_numbers": [],
            "label": "HKC Alarm System",
            "multi_view": False,
            "inputs": [],
            "kind": "panel",
        }
    ]


def test_build_alarm_views_multi_user_uses_block_descriptions():
    views = build_alarm_views(
        ["1111", "2222"],
        {
            1111: {"allowedBlocks": [{"block": 1, "description": "Main House"}]},
            2222: {"allowedBlocks": [{"block": 2, "description": "Guest Suite"}]},
        },
        supports_multi_view=True,
    )

    assert views[0]["label"] == "Main House"
    assert views[1]["label"] == "Guest Suite"


def test_build_alarm_views_single_user_with_entity_map_stays_single_device():
    views = build_alarm_views(
        ["1234"],
        entity_map={
            "blocks": [
                {
                    "block": 1,
                    "description": "Block 1",
                    "accessUserCodes": [1234],
                    "inputs": [{"inputId": "1", "description": "Zone 1"}],
                }
            ]
        },
        supports_multi_view=True,
    )

    assert len(views) == 1
    assert views[0]["multi_view"] is False
    assert views[0]["key"] == "default"


def test_build_alarm_views_prefers_entity_map_blocks():
    views = build_alarm_views(
        ["1111", "2222"],
        entity_map={
            "blocks": [
                {
                    "block": 2,
                    "description": "House 2",
                    "accessUserCodes": [2222],
                    "inputs": [{"inputId": "16", "description": "Zone 16"}],
                }
            ]
        },
        supports_multi_view=True,
    )

    assert views == [
        {
            "key": "block_2",
            "user_code": "2222",
            "allowed_user_codes": ["2222"],
            "block_numbers": [2],
            "label": "House 2",
            "multi_view": True,
            "inputs": [{"inputId": "16", "description": "Zone 16"}],
            "kind": "block",
        }
    ]
