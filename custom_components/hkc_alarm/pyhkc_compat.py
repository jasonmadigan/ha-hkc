"""Compatibility helpers for different pyhkc versions."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from functools import partial
from typing import Any

from pyhkc.hkc_api import HKCAlarm

_LOGGER = logging.getLogger(__name__)


def _supports_keyword(callable_obj: Callable[..., Any], keyword: str) -> bool:
    """Return True when a callable accepts a named keyword argument."""
    try:
        return keyword in inspect.signature(callable_obj).parameters
    except (TypeError, ValueError):
        return False


def build_hkc_alarm(
    panel_id: str,
    panel_password: str,
    user_code: str,
    additional_user_codes: list[str] | None = None,
    request_timeout: int | None = None,
) -> HKCAlarm:
    """Create an HKCAlarm instance across pyhkc versions."""
    additional_user_codes = additional_user_codes or []
    kwargs: dict[str, Any] = {}

    if _supports_keyword(HKCAlarm, "user_codes"):
        kwargs["user_codes"] = additional_user_codes
    if request_timeout is not None and _supports_keyword(HKCAlarm, "request_timeout"):
        kwargs["request_timeout"] = request_timeout

    try:
        return HKCAlarm(panel_id, panel_password, user_code, **kwargs)
    except Exception:
        if "user_codes" in kwargs and additional_user_codes:
            _LOGGER.warning(
                "pyhkc failed to initialize with additional user codes for panel %s; "
                "falling back to legacy single-user mode",
                panel_id,
                exc_info=True,
            )
            kwargs.pop("user_codes", None)
            return HKCAlarm(panel_id, panel_password, user_code, **kwargs)
        raise


def build_alarm_command(
    alarm_command: Callable[..., Any],
    user_code: str,
    primary_user_code: str,
) -> Callable[[], Any]:
    """Build a callable that executes an alarm command compatibly."""
    if _supports_keyword(alarm_command, "user_code"):
        return partial(alarm_command, user_code=user_code)

    if user_code != primary_user_code:
        raise TypeError("installed_pyhkc_does_not_support_multi_user")

    return alarm_command


def get_status_for_user(hkc_alarm: HKCAlarm, user_code: str) -> dict:
    """Fetch status for a specific user when supported."""
    if _supports_keyword(hkc_alarm.get_system_status, "user_code"):
        return hkc_alarm.get_system_status(user_code=user_code)
    return hkc_alarm.get_system_status()


def get_inputs_for_user(hkc_alarm: HKCAlarm, user_code: str) -> list[dict]:
    """Fetch inputs for a specific user when supported."""
    if _supports_keyword(hkc_alarm.get_all_inputs, "user_code"):
        return hkc_alarm.get_all_inputs(user_code=user_code)
    return hkc_alarm.get_all_inputs()


def get_user_access_summary(
    hkc_alarm: HKCAlarm,
    user_codes: list[str],
    statuses_by_user: dict[str, dict] | None = None,
) -> dict[int, dict]:
    """Return per-user access summary across pyhkc versions."""
    if hasattr(hkc_alarm, "get_user_access_summary"):
        return hkc_alarm.get_user_access_summary(user_codes=[int(code) for code in user_codes])

    statuses_by_user = statuses_by_user or {
        code: get_status_for_user(hkc_alarm, code) for code in user_codes
    }
    summaries: dict[int, dict] = {}
    for code in user_codes:
        status = statuses_by_user[code]
        descriptions = status.get("descriptions", {})
        allowed_blocks = []
        denied_blocks = []
        for block_number, block in enumerate(status.get("blocks", []), start=1):
            if not block.get("isEnabled"):
                continue

            summary = {
                "block": block_number,
                "description": descriptions.get(
                    f"block{block_number}", f"Block {block_number}"
                ),
                "armState": block.get("armState"),
            }
            if block.get("userAllowed", True):
                allowed_blocks.append(summary)
            else:
                denied_blocks.append(summary)

        summaries[int(code)] = {
            "userOptions": status.get("userOptions", {}),
            "allowedBlocks": allowed_blocks,
            "deniedBlocks": denied_blocks,
        }

    return summaries


def get_home_assistant_entity_map(
    hkc_alarm: HKCAlarm,
    user_codes: list[str],
) -> dict | None:
    """Return the upstream Home Assistant entity map when supported."""
    if hasattr(hkc_alarm, "get_home_assistant_entity_map"):
        try:
            return hkc_alarm.get_home_assistant_entity_map(
                user_codes=[int(code) for code in user_codes]
            )
        except Exception:
            _LOGGER.warning("failed to fetch entity map", exc_info=True)
    return None


def get_device_details(hkc_alarm: HKCAlarm) -> dict:
    """Return device details when supported."""
    if hasattr(hkc_alarm, "get_device_details"):
        try:
            return hkc_alarm.get_device_details() or {}
        except Exception:
            _LOGGER.warning("failed to fetch device details", exc_info=True)
    return {}


def get_remote_keypad(hkc_alarm: HKCAlarm) -> dict:
    """Return the current keypad payload when supported."""
    if hasattr(hkc_alarm, "get_remote_keypad"):
        try:
            return hkc_alarm.get_remote_keypad() or {}
        except Exception:
            _LOGGER.warning("failed to fetch remote keypad", exc_info=True)

    if hasattr(hkc_alarm, "get_panel"):
        try:
            return hkc_alarm.get_panel() or {}
        except Exception:
            _LOGGER.warning("failed to fetch panel payload", exc_info=True)

    return {}


def get_outputs(hkc_alarm: HKCAlarm) -> list[dict]:
    """Return outputs when supported."""
    if hasattr(hkc_alarm, "get_outputs"):
        try:
            return hkc_alarm.get_outputs() or []
        except Exception:
            _LOGGER.warning("failed to fetch outputs", exc_info=True)
    return []


def get_temporary_user(hkc_alarm: HKCAlarm, user_code: str | None = None) -> dict:
    """Return temporary user details when supported."""
    if hasattr(hkc_alarm, "get_temporary_user"):
        try:
            if user_code is not None and _supports_keyword(hkc_alarm.get_temporary_user, "user_code"):
                return hkc_alarm.get_temporary_user(user_code=user_code) or {}
            return hkc_alarm.get_temporary_user() or {}
        except Exception:
            _LOGGER.warning("failed to fetch temporary user", exc_info=True)
    return {}


def build_block_alarm_command(
    hkc_alarm: HKCAlarm,
    command_name: str,
    user_code: str,
    primary_user_code: str,
    block_number: int | None,
) -> Callable[[], Any]:
    """Build a callable that targets a specific HKC block when supported."""
    command_map = {
        "disarm": 0,
        "arm_partset_a": 1,
        "arm_partset_b": 2,
        "arm_fullset": 3,
    }

    if block_number is None:
        return build_alarm_command(
            getattr(hkc_alarm, command_name),
            user_code,
            primary_user_code,
        )

    alarm_command = getattr(hkc_alarm, "_arm_or_disarm", None)
    if alarm_command is None:
        raise TypeError("installed_pyhkc_does_not_support_block_commands")

    zero_based_block = max(block_number - 1, 0)
    if _supports_keyword(alarm_command, "user_code"):
        return partial(
            alarm_command,
            command=command_map[command_name],
            block=zero_based_block,
            user_code=user_code,
        )

    if user_code != primary_user_code or zero_based_block != 0:
        raise TypeError("installed_pyhkc_does_not_support_block_commands")

    return partial(alarm_command, command=command_map[command_name], block=0)
