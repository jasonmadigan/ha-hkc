# HKC Alarm Integration for Home Assistant

This repository contains an unofficial Home Assistant integration for [HKC Alarm](https://www.hkcsecurity.com/) systems, allowing you to control and monitor your HKC Alarm directly from Home Assistant.

## Installation

You will need [HACS](https://hacs.xyz) installed in your Home Assistant server. Install the integration by installing this repository as a Custom Repository. Then, navigate to Integrations, Add an Integration and select HKC Alarm. You will then be asked to enter:

* **Panel ID**: Your HKC Alarm Panel ID.
* **Panel Password**: Your HKC Alarm Panel Password.
* **Alarm Code**: Your HKC Alarm Code.
* **Update Interval (seconds)**: (Optional) Custom update interval for fetching data from HKC Alarm. Default is 60 seconds. Recommend keeping this at 60s, as this is similar to the Mobile App's polling interval, and we want to respect HKC's API.

[![Open your Home Assistant instance and add this integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=hkc_alarm)

## Entities

The integration updates data every minute by default. It exposes the following entities:

* An alarm control panel entity representing the HKC Alarm system.
* Sensor entities for each input on the HKC Alarm system.

The *State* of the alarm control panel is either `armed_home`, `armed_away`, or `disarmed`. The sensor entities will have states `Open` or `Closed` based on the state of the corresponding input on the HKC Alarm system.

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
      title: 🚨 HKC Alarm Notification 🚨
      message: >
        Alarm System is now {{ states('alarm_control_panel.hkc_alarm_system') }}
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

- [Github Repository](https://github.com/jasonmadigan/pyhkc)
- [HKC Alarm PyPi Package](https://pypi.org/project/pyhkc/)