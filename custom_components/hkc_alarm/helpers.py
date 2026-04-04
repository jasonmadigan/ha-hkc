"""Helpers for HKC Alarm configuration."""

from __future__ import annotations

import re
from collections.abc import Iterable


class InvalidUserCodeError(ValueError):
    """Raised when a configured user code is invalid."""


def _normalize_user_code(user_code: str) -> str:
    code = str(user_code).strip()
    if not code or not code.isdigit():
        raise InvalidUserCodeError
    return code


def parse_additional_user_codes(raw_codes: str | Iterable[str] | None) -> list[str]:
    """Parse and validate additional HKC user codes."""
    if raw_codes is None:
        return []

    if isinstance(raw_codes, str):
        values = [value for value in re.split(r"[\n,;]+", raw_codes) if value.strip()]
    else:
        values = list(raw_codes)

    return [_normalize_user_code(value) for value in values]


def normalize_configured_user_codes(
    primary_user_code: str,
    additional_user_codes: str | Iterable[str] | None = None,
) -> list[str]:
    """Return a de-duplicated, validated list of configured user codes."""
    ordered_codes = [_normalize_user_code(primary_user_code)]
    ordered_codes.extend(parse_additional_user_codes(additional_user_codes))

    unique_codes: list[str] = []
    for code in ordered_codes:
        if code not in unique_codes:
            unique_codes.append(code)

    return unique_codes


def serialize_user_codes(user_codes: Iterable[str]) -> str:
    """Convert stored user codes to an options-form string."""
    return ", ".join(str(code) for code in user_codes)


def get_panel_display_name(device_details: dict | None, fallback: str = "HKC Alarm System") -> str:
    """Return a friendly panel name for Home Assistant."""
    device_details = device_details or {}
    site_name = str(device_details.get("siteName", "")).strip()
    installation_name = str(device_details.get("installationName", "")).strip()
    return site_name or installation_name or fallback


def build_device_metadata(device_details: dict | None, outputs: list[dict] | None = None) -> dict:
    """Normalize upstream panel metadata for entity/device presentation."""
    device_details = device_details or {}
    outputs = outputs or []
    return {
        "panel_name": get_panel_display_name(device_details),
        "model": f"HKC {device_details.get('type', 'Alarm')} / Variant {device_details.get('variant', 'Unknown')}",
        "sw_version": str(device_details.get("version", "1.0.0")),
        "serial_number": str(device_details.get("serialNumber", "")) or None,
        "installation_name": str(device_details.get("installationName", "")).strip() or None,
        "site_name": str(device_details.get("siteName", "")).strip() or None,
        "platform": device_details.get("platform"),
        "country_code": device_details.get("countryCode"),
        "language": device_details.get("language"),
        "audiolib_version": device_details.get("audiolibVersion"),
        "output_count": len(outputs),
    }


def build_alarm_views(
    configured_user_codes: list[str],
    access_summary: dict[int, dict] | None = None,
    entity_map: dict | None = None,
    supports_multi_view: bool = False,
) -> list[dict]:
    """Build logical alarm views from configured user codes."""
    if entity_map and entity_map.get("blocks"):
        views: list[dict] = []
        for block in entity_map["blocks"]:
            access_user_codes = [str(code) for code in block.get("accessUserCodes", [])]
            if not access_user_codes:
                continue
            views.append(
                {
                    "key": f"block_{block['block']}",
                    "user_code": access_user_codes[0],
                    "allowed_user_codes": access_user_codes,
                    "block_numbers": [int(block["block"])],
                    "label": block.get("description") or f"Block {block['block']}",
                    "multi_view": True,
                    "inputs": list(block.get("inputs", [])),
                    "kind": "block",
                }
            )

        return views

    if len(configured_user_codes) <= 1 or not supports_multi_view:
        return [
            {
                "key": "default",
                "user_code": configured_user_codes[0],
                "allowed_user_codes": [configured_user_codes[0]],
                "block_numbers": [],
                "label": "HKC Alarm System",
                "multi_view": False,
                "inputs": [],
                "kind": "panel",
            }
        ]

    views: list[dict] = []
    access_summary = access_summary or {}
    for code in configured_user_codes:
        summary = access_summary.get(int(code), {})
        allowed_blocks = summary.get("allowedBlocks", [])
        block_numbers = [
            int(block["block"])
            for block in allowed_blocks
            if block.get("block") is not None
        ]

        if len(allowed_blocks) == 1:
            label = allowed_blocks[0].get("description") or f"Block {block_numbers[0]}"
        else:
            label = f"HKC Alarm {code}"

        views.append(
            {
                "key": f"user_{code}",
                "user_code": code,
                "allowed_user_codes": [code],
                "block_numbers": block_numbers,
                "label": label,
                "multi_view": True,
                "inputs": [],
                "kind": "user",
            }
        )

    return views
