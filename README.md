# BCone Home Assistant Integration

Production workspace for a HACS-installable Home Assistant integration for
BCone.

Initial target: credential-only monitoring. Users enter their BCone
email/password once; the integration signs in with Cognito, stores refresh
tokens, discovers the BCone `deviceId` through the app API, and polls recent
device history for decoded hub and pool-unit state.

## Status

This repository is being initialized from the BCone research workspace. The
first production milestone is a custom integration with:

- config flow that asks only for BCone account credentials
- Cognito token storage/refresh; the password is not stored
- automatic device ID discovery through `/api/getRelevantDeviceId`
- read-only state from `/api/getDeviceHistory`
- optional live MQTT state when local mTLS credential files are present
- decoded hub and pool-unit state entities
- guarded MQTT controls for pool-unit state, stop siren, and pool-unit sensitivity
- Home Assistant alarm control panel entities for pool-unit security surfaces
- optional Lovelace card served from `/bcone/bcone-card.js`
- redacted diagnostics

The app also uses AWS IoT MQTT topics including `bc/<device_id>/ind`,
`bc/<device_id>/updatefwstat`, and `FW`. MQTT support is gated on local
credential files. Without those files, the integration stays REST-only and
state-changing controls are unavailable.

Optional MQTT credential paths under Home Assistant config:

- `/config/bcone_mqtt_auth/AmazonRootCA1.pem`
- `/config/bcone_mqtt_auth/client.crt`
- `/config/bcone_mqtt_auth/private.key`

If any of those files are missing, the integration stays REST-only and the
`MQTT Connected` entity remains off.

## Lovelace Card

The integration serves a no-build custom card at:

```text
/bcone/bcone-card.js
```

Add that URL as a Lovelace JavaScript module resource after installing or
updating the integration and restarting Home Assistant.

Example card configuration:

```yaml
type: custom:bcone-pool-card
name: Pool
state_entity: select.pool_state
sensitivity_entity: number.pool_sensitivity
stop_siren_entity: button.bcone_stop_siren
temperature_entity: sensor.pool_temperature
battery_entity: sensor.pool_battery_voltage
rssi_entity: sensor.pool_rssi
position_entity: sensor.pool_position
```

Only `state_entity` is required. The card tries to find related entities from
the same Home Assistant device when the frontend entity registry is available,
but explicit entity ids are more predictable.

HACS installs this repository as an integration, so it does not automatically
register the card as a Lovelace frontend plugin. Add the resource manually from
Home Assistant dashboards as a JavaScript module.

## Security

Each discovered pool unit also exposes an `alarm_control_panel` entity so Home
Assistant can classify it as a security device:

- `armed_away`: BCone `On/Armed`
- `disarmed`: BCone `Off/Disarmed`
- `armed_custom_bypass`: BCone `Swim Mode`
- `triggered`: pool-unit alarm flag is active

## Safety

Do not commit account data, tokens, private device IDs, raw captures, payload
values, MQTT configs, or PEM files.
