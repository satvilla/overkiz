[![HACS][hacsbadge]][hacs]
[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]][license]

# ![HA][ha-logo] Overkiz - Home Assistant Integration

A customized version of the Home Assistant Overkiz integration, focused on improving support for **Atlantic and Thermor heating and cooling systems using Cozytouch**.

This project is based on the official Home Assistant Overkiz integration and extends its functionality to provide better support for devices and features that are not fully exposed or controllable through the standard integration.

---

## 🔥 Atlantic / Thermor Cozytouch

This project has been developed and tested primarily with **Atlantic and Thermor Cozytouch** systems, including heating and cooling zones based on:

* `io:AtlanticPassAPCHeatingAndCoolingZoneComponent`

The main goal is to provide reliable control of heating and cooling zones from Home Assistant while preserving the device state reported by the Cozytouch platform.

### Supported functionality

The customized implementation provides support for:

* Heating and cooling operating modes
* Heating and cooling target temperatures
* Comfort temperature
* Eco temperature
* Absence temperature
* Preset modes
* Absence mode
* Heating and cooling profiles
* Current operating mode
* Device state synchronization
* Execution tracking
* Multiple commands associated with the same device
* Improved handling of Overkiz command execution and state updates

---

## 🌡️ Temperature Control

The integration improves temperature control for Atlantic/Thermor heating and cooling zones.

The following temperature concepts are handled independently where supported by the device:

* **Comfort heating temperature**
* **Eco heating temperature**
* **Comfort cooling temperature**
* **Eco cooling temperature**
* **Derogated temperature**
* **Absence temperature**

Temperature values are validated and constrained to the ranges accepted by the device before commands are sent to Cozytouch.

This prevents invalid values from being sent to the Overkiz API and allows Home Assistant's climate controls to expose a more appropriate temperature range.

---

## 🏠 Absence Mode

Specific work has been carried out on the handling of the device's absence functionality.

The integration supports setting and managing the absence temperature while keeping the Home Assistant climate entity synchronized with the state reported by Cozytouch.

The implementation also prevents recursive calls between preset and absence-mode handling.

---

## ⚙️ Improved Command Execution

The Overkiz command execution layer has been extended and adapted to provide more reliable handling of commands sent to individual devices.

The custom executor supports:

* Single command execution
* Multiple commands in a single action group
* Execution tracking
* Command cancellation
* Optional state refresh after command execution
* Association of executions with the corresponding device and command

Multiple commands can therefore be grouped into a single Overkiz action group when appropriate.

---

## 🔄 Improved State Updates

The coordinator has been adapted to better handle Overkiz events and command executions.

The implementation takes into account:

* Device events
* Execution registration
* Execution state changes
* Completed executions
* Failed executions
* Dynamic update intervals while commands are being executed

This allows Home Assistant to continue receiving updated device state without unnecessarily polling the Overkiz platform at a high frequency.

The implementation uses event-driven updates where possible and applies a controlled minimum interval while an execution is in progress.

---

## 🧩 Why This Project Exists

The standard Home Assistant Overkiz integration provides broad support for the Overkiz ecosystem, but some devices expose functionality that is difficult to control correctly through the generic implementation.

In particular, Atlantic/Thermor Cozytouch heating and cooling zones can expose several different temperature targets and operating modes.

The work in this repository focuses on making these capabilities usable from Home Assistant's `climate` platform.

The development has been driven by testing against a real Atlantic/Thermor Cozytouch installation and by analysing the commands, states, events and device definitions exposed by the Overkiz API.

---

## 🚀 Installation

### HACS Custom Repository

This project can be installed through [HACS][hacs].

After installing HACS, open the **HACS → Integrations** section and add:

```text
https://github.com/satvilla/overkiz
```

as a **Custom Repository** with the category:

```text
Integration
```

After adding the repository, install **Overkiz** and restart Home Assistant.

> **Note:** This is currently a custom version of the Overkiz integration and is intended primarily for testing and development.

### Manual Installation

1. Open your Home Assistant configuration directory.
2. If it does not already exist, create a `custom_components` directory.
3. Create a directory called `overkiz` inside `custom_components`.
4. Copy the contents of `custom_components/overkiz/` from this repository into that directory.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Integrations**.
7. Configure or reload the Overkiz integration.

The resulting structure should look like:

```text
config/
└── custom_components/
    └── overkiz/
        ├── __init__.py
        ├── manifest.json
        ├── climate.py
        └── ...
```

---

## 🧪 Development and Testing

Development has been performed using:

* Home Assistant
* Home Assistant OS
* Python
* `pyoverkiz`
* Atlantic Cozytouch
* Thermor Cozytouch

Particular attention has been given to the behaviour of:

```text
io:AtlanticPassAPCHeatingAndCoolingZoneComponent
```

including its thermal configuration, operating modes, temperature profiles and available commands.

The implementation has also been tested against the Overkiz execution and event mechanisms to ensure that commands and resulting state changes are correctly synchronized with Home Assistant.

---

## 🪲 Debugging

To enable debug logging for this integration, add the following to `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.overkiz: debug
```

Restart Home Assistant after changing the logging configuration.

Debug logs can be particularly useful when investigating:

* Device discovery
* Available commands
* Device states
* Overkiz executions
* Execution events
* Temperature changes
* Heating/cooling mode changes
* Cozytouch communication problems

---

## ⚠️ Important

This repository is a **custom development version** of the Home Assistant Overkiz integration.

It has been developed primarily around Atlantic/Thermor Cozytouch heating and cooling devices. Other Overkiz-compatible devices may continue to work, but they have not necessarily been tested with the changes in this repository.

Use this integration at your own risk, particularly in production heating or cooling systems.

---

## 🙋 Contributions and Feedback

Issues, testing and feedback are welcome.

If you encounter a problem, please include:

* Home Assistant version
* Device manufacturer and model
* Overkiz device type
* Relevant debug logs
* The operation that was being performed when the problem occurred

This information makes it much easier to reproduce and investigate device-specific behaviour.

---

## 🙏 Acknowledgements

This project is based on the **Overkiz integration originally developed for Home Assistant** and the work of the Home Assistant and pyoverkiz communities.

The purpose of this repository is to extend and improve support for specific Overkiz devices and functionality, particularly Atlantic and Thermor Cozytouch heating and cooling systems.

---

[hacs]: https://hacs.xyz/
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/v/release/satvilla/overkiz?display_name=release&include_prereleases&style=for-the-badge
[releases]: https://github.com/satvilla/overkiz/releases
[commits-shield]: https://img.shields.io/github/last-commit/satvilla/overkiz?style=for-the-badge
[commits]: https://github.com/satvilla/overkiz/commits/main
[license-shield]: https://img.shields.io/github/license/satvilla/overkiz.svg?style=for-the-badge
[license]: https://github.com/satvilla/overkiz/blob/main/LICENSE
[ha-logo]: https://brands.home-assistant.io/_/homeassistant/icon.png
