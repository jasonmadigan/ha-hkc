"""Constants for the HKC Alarm integration."""

# Integration domain identifier. This is the name used in the configuration.yaml file.
DOMAIN = "hkc_alarm"
EVENT_ALARM_COMMAND_EXECUTED = "hkc_alarm_command_executed"
DEFAULT_UPDATE_INTERVAL = 60  # Default update interval in seconds
MIN_UPDATE_INTERVAL = 30  # Minimum update interval in seconds
CONF_UPDATE_INTERVAL = "update_interval"
CONF_ADDITIONAL_USER_CODES = "additional_user_codes"
CONF_REQUIRE_USER_PIN = "require_user_pin"
DEFAULT_REQUIRE_USER_PIN = False
