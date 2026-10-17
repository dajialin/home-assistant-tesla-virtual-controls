# Changelog

## 3.4.3

- Classify the single-vehicle integration as a device instead of a helper so its configured entry appears in Settings → Devices & services → Integrations.
- Preserve the existing config entry, internal domain, VIN-scoped unique IDs, eight entities, and TeslaMate/Fleet behavior; no reconfiguration is required.
- Add a regression test for the integration type. Restart Home Assistant after upgrading to refresh the cached manifest classification.

## 3.4.2

- Serialize every active stateful control per entity so rapid commands preserve invocation order; toggle-based trunk state is checked under the same lock both before and after wake-up.
- Publish climate mode, target temperature, and climate-keeper preset optimistically only after successful Fleet service completion.
- Keep climate optimism isolated per field: unrelated or invalid telemetry does not erase it, while the next changed valid value from that field's configured TeslaMate source becomes authoritative.
- Preserve source state after every failed command and keep Tesla Fleet periodic polling disabled.

## 3.4.1

- Update the sentry-mode switch immediately after a successful Tesla Fleet command response.
- Keep failed commands from changing the displayed state, and let every later TeslaMate MQTT state change override the optimistic command state.
- Serialize sentry commands so rapid opposite requests update state in invocation order.

## 3.4.0

- Remove the four custom seat controls and the custom steering-wheel heater, including their entity-registry and restore-state records during config-entry migration.
- Keep sentry-mode display state exclusively synchronized with the configured TeslaMate MQTT entity instead of optimistically overwriting it after commands.
- Retain Tesla Fleet only for explicit sentry commands; no vehicle command is used for state verification.

## 3.3.1

- Correct the TeslaMate lock-class binary-sensor mapping so `on`/unlocked and `off`/locked produce the matching Home Assistant lock state.

## 3.3.0

- Make TeslaMate the only state/telemetry source for climate and vehicle controls.
- Keep Tesla Fleet exclusively for explicit command execution and vehicle identity, minimizing API quota usage.
- Require polling to be disabled in Tesla Fleet System options without mutating that shared integration setting.
- Restore seat and steering modes locally because TeslaMate does not publish those states.
- Rename all 13 entity IDs to ordinary `tesla_*` names while retaining stable VIN-scoped unique IDs.
- Rename the default device to **Tesla Controls** while preserving custom user names.
- Add TeslaMate source selectors to Config Flow and Options Flow in every bundled locale.
- Correct Simplified/Traditional Chinese and Japanese entity labels.
- Add distinct open/closed icons for trunk, frunk, charge-port door, and windows.

## 3.2.1

- Rename the user-facing integration from **Tesla Virtual HVAC** to **Tesla Virtual Controls**.
- Preserve the internal `tesla_virtual_hvac` domain for non-destructive upgrades.
- Automatically migrate the former default config-entry and device name while preserving custom names.
- Add repository metadata, documentation, lint configuration, and CI.

## 3.2.0

- Add steering-wheel heating with off, low, high, and automatic modes.
- Add trunk, frunk, charge-port door, and window covers.
- Add sentry-mode switch, vehicle lock, and charge-limit number.
- Serialize seat and steering transitions to prevent command interleaving.

## 3.1.0

- Provide exactly four virtual seat controls.
- Add automatic mode to both front seats.
- Keep both rear seats heater-only and remove the obsolete rear-center entity.
