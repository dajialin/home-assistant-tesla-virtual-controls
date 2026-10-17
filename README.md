# Tesla Virtual Controls

A Home Assistant custom integration designed to conserve the Tesla Fleet API quota: **TeslaMate telemetry** supplies vehicle state, while **Tesla Fleet commands** are used only when the user asks the car to do something.

> **Compatibility note:** the integration's internal Home Assistant domain remains `tesla_virtual_hvac`. Stable VIN-scoped unique IDs are also retained so existing config entries, devices, registry records, automations, and dashboards can upgrade in place. The visible device and entity IDs no longer contain the word `virtual`.

## Architecture and quota behavior

- Climate state, cabin temperature, target temperature, and climate-keeper mode come from TeslaMate-backed Home Assistant entities. Successful climate commands temporarily override only their affected fields until those configured sources publish changed valid values.
- Trunk, frunk, charge-port door, windows, sentry mode, lock, and charge-limit state follow TeslaMate MQTT entities, with temporary optimistic state after successful commands until the next source state change.
- Tesla Fleet is retained as the command transport and vehicle identity source.
- The selected Tesla Fleet config entry must have **polling disabled in its System options**. The bridge refuses to load otherwise and never mutates this shared setting. Home Assistant still performs its required initial refresh at startup, but it does not schedule periodic vehicle-data refreshes.
- No custom entity reads its displayed state from Tesla Fleet telemetry.
- Waking the vehicle and calling Tesla Fleet happen only during an explicit command.

This split minimizes Tesla Fleet API quota usage without weakening command validation or VIN scoping.

## Requirements

- Home Assistant **2026.8.3** or newer
- The official **Tesla Fleet** integration configured for the vehicle
- Tesla Fleet command scopes required by the controls you intend to use
- TeslaMate MQTT entities for climate and vehicle state

The default TeslaMate state entities are:

```text
binary_sensor.tesla_is_climate_on
sensor.tesla_inside_temp
sensor.tesla_driver_temp
sensor.tesla_climate_keeper_mode
binary_sensor.tesla_trunk_open
binary_sensor.tesla_frunk_open
binary_sensor.tesla_charge_port_door_open
binary_sensor.tesla_windows_open
binary_sensor.tesla_locked
binary_sensor.tesla_sentry_mode
sensor.tesla_charge_limit_soc
```

Every source can be changed through the integration's Options Flow.

## Entities

The integration creates one VIN-scoped **Tesla Controls** device with 8 entities:

| Entity ID | Behavior / state source |
|---|---|
| `climate.tesla_climate` | Climate commands; successful commands update affected fields immediately, then each field follows its TeslaMate source |
| `cover.tesla_trunk` | Open and close; optimistic after success, then follows TeslaMate |
| `cover.tesla_frunk` | Open only; optimistic after success, then follows TeslaMate |
| `cover.tesla_charge_port_door` | Open and close; optimistic after success, then follows TeslaMate |
| `cover.tesla_windows` | Open means vent, close means close all windows; optimistic after success, then follows TeslaMate |
| `switch.tesla_sentry_mode` | Enable and disable; optimistic after success, then follows TeslaMate |
| `lock.tesla_vehicle` | Lock and unlock; optimistic after success, then follows TeslaMate |
| `number.tesla_charge_limit` | 50–100%, step 1%; optimistic after success, then follows TeslaMate |

## Safety behavior

- Every entity checks the relevant Tesla Fleet command scope before acting.
- Commands wake the vehicle when necessary and propagate Fleet API failures to Home Assistant.
- Successful stateful commands update the displayed value only after Fleet confirms completion; failed commands leave the existing source-derived state unchanged.
- Covers, sentry mode, vehicle lock, and charge limit continue to apply later TeslaMate state events with fail-closed parsing.
- Climate optimism is isolated per field and yields only when that corresponding configured source publishes a changed valid value; unrelated, same-value, and invalid events preserve the overlay.
- Commands are serialized per entity so rapid requests cannot finish out of order. Trunk state is checked under the same lock both before and after wake-up to prevent duplicate, skipped, or stale toggle commands.
- The frunk intentionally exposes only `open_cover`; Tesla cannot remotely latch it closed.
- Rear-trunk toggle commands are sent only when TeslaMate does not already show the requested state.
- Tests mock every Tesla command and never operate a real vehicle.

## Languages and icons

Entity and configuration resources are structurally complete for every bundled locale. English, Japanese, Korean, Simplified Chinese, and Traditional Chinese have maintained labels for the TeslaMate sources. Cover icons distinguish open and closed states for the trunk, frunk, charge-port door, and windows.

Home Assistant stores an entity's original name using the server's Core language. Per-user frontend language does not rewrite an already stored registry name; changing the Core language and reloading the integration updates those original names.

## Installation

### Manual

1. Copy `custom_components/tesla_virtual_hvac` into `/config/custom_components/`.
2. In the Tesla Fleet integration's **System options**, turn off polling.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration**.
5. Search for **Tesla Virtual Controls**.
6. Select the Tesla Fleet command entity and TeslaMate telemetry entities.

### Existing installation

Copy the new `tesla_virtual_hvac` directory over the existing directory and restart Home Assistant. Do **not** rename the directory. The integration migrates the default device name to **Tesla Controls** and changes entity IDs to ordinary `tesla_*` names while preserving unique IDs. Custom device names are preserved.

Starting with **3.4.3**, the integration is classified as a single-vehicle **device**, not a helper. After upgrading and restarting Home Assistant, its card appears under **Settings → Devices & services → Integrations** as **Tesla Virtual Controls**; the existing config-entry title may be **Tesla Controls**. Earlier releases were classified as helpers and did not appear in the integrations overview. Existing entries, entity IDs, and settings are retained; do not delete or re-add the integration.

## Development

The verified targets are Home Assistant 2026.8.3, Python 3.14, and `tesla-fleet-api` 1.7.6.

```bash
python -m unittest discover -s tests -v
python -m compileall -q custom_components/tesla_virtual_hvac
ruff check custom_components/tesla_virtual_hvac tests
ruff format --check custom_components/tesla_virtual_hvac tests
```

GitHub Actions runs the same checks without sending vehicle commands.
