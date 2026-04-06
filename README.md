# HKC Alarm Integration for Home Assistant

> [!CAUTION]
> This integration is only recommended for HKC users who have an alarm system with HKC's WiFi card, rather than users who are purely using GSM. GSM-only users will encounter rate limiting from HKC, so it isn't advisable to use unless you are certain you are WiFi + GSM.

> [!CAUTION]
> This integration is provided as-is, with no warranty or support, and is not in any way associated nor endorsed by HKC. Users assume all risk in using this integration. HKC could, for all I know, block their users from using this or their app at any time. That said, many users have been successfully using this integration for almost a year now (as of Sept 2024).

This repository contains an unofficial Home Assistant integration for [HKC Alarm](https://www.hkcsecurity.com/) systems, allowing you to control and monitor your HKC Alarm directly from Home Assistant. 

## Installation

You will need [HACS](https://hacs.xyz) installed in your Home Assistant server. Install the integration by installing this repository as a Custom Repository. Then, navigate to Integrations, Add an Integration and select HKC Alarm. You will then be asked to enter:

* **Panel ID**: Your HKC Alarm Panel ID (same as panel ID in HKC mobile app)
* **Panel Password**: Your HKC Alarm Panel Password (same as panel password from HKC mobile app)
* **Alarm Code**: Your HKC Alarm Code/PIN
* **Additional User PINs**: (Optional) Extra HKC user PINs separated by commas to enable multi-user arm/disarm from Home Assistant
* **Require entering a user PIN to arm/disarm**: (Optional) Forces the Home Assistant alarm panel card keypad to be used for control
* **Update Interval (seconds)**: (Optional) Custom update interval for fetching data from HKC Alarm. Default is 60 seconds. Recommend keeping this at 60s, as this is similar to the Mobile App's polling interval, and we want to respect HKC's API.

[![Open your Home Assistant instance and add this integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=hkc_alarm)

## Entities

The integration updates data every minute by default. It exposes the following entities:

* An alarm control panel entity representing the HKC Alarm system.
* Sensor entities for each input on the HKC Alarm system.

The *State* of the alarm control panel is either `armed_home`, `armed_away`, `armed_night` or `disarmed`. The sensor entities will have states `Open` or `Closed` based on the state of the corresponding input on the HKC Alarm system.

- `armed_away` maps to "Full Set"
- `armed_home` maps to "Partset A"
- `armed_night` maps to "Partset B"
- `disarmed` maps to, as you'd expect, "Disarmed"

## Multi-user and PIN entry

The integration now supports two Home Assistant alarm panel workflows:

* If you configure multiple HKC user PINs and your panel users have access to different blocks, the integration will create separate alarm views for those homes/areas and will only expose the sensors returned for each configured user.
* If you enable **Require entering a user PIN to arm/disarm**, the standard Home Assistant [alarm panel card](https://www.home-assistant.io/dashboards/alarm-panel/) keypad is used before control actions are sent.

## Command feedback

When an arm/disarm command returns a success response from the API, the integration immediately updates the alarm entity state so existing state-based automations react without waiting for the coordinator refresh.

The integration also exposes command feedback metadata via `Last Command`, `Last Command State`, `Last Command Result`, `Last Command Result Code`, `Last Command Acknowledged`, and `Last Command At` attributes.

The alarm state is still confirmed by the coordinator refresh after command completion.

## Sample Automation to notify about alarm state changes

```yaml
alias: HKC Alarm State Notifications
description: ""
trigger:
  - platform: state
    entity_id: alarm_control_panel.hkc_alarm_system
condition: []
action:
  - service: notify.notify
    data:
      title: HKC Alarm Status
      message: >
        Alarm is now {{ states('alarm_control_panel.hkc_alarm_system') }}.
mode: single
```


## Troubleshooting

If you encounter issues with this integration, you can enable debug logging for this component by adding the following lines to your `configuration.yaml` file:

```yaml
logger:
  logs:
    custom_components.hkc_alarm: debug
```

This will produce detailed debug logs which can help in diagnosing the problem.

## Links

- [pyhkc](https://github.com/jasonmadigan/pyhkc)
- [HKC Alarm PyPi Package](https://pypi.org/project/pyhkc/)
