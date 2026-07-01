# BCone Home Assistant Integration

Production workspace for a HACS-installable Home Assistant integration for
BCone.

Initial target: credential-only read-only monitoring. Users enter their BCone
email/password once; the integration signs in with Cognito, stores refresh
tokens, discovers the BCone `deviceId` through the app API, and polls recent
device history for decoded hub and pool-unit state.

## Status

This repository is being initialized from the BCone research workspace. The
first production milestone is a read-only custom integration with:

- config flow that asks only for BCone account credentials
- Cognito token storage/refresh; the password is not stored
- automatic device ID discovery through `/api/getRelevantDeviceId`
- read-only state from `/api/getDeviceHistory`
- optional live MQTT state when local mTLS credential files are present
- decoded hub and pool-unit state entities
- redacted diagnostics
- no Home Assistant services and no MQTT publish calls

The app also uses AWS IoT MQTT topics including `bc/<device_id>/ind`,
`bc/<device_id>/updatefwstat`, and `FW`. MQTT support is gated on local
credential files and is strictly passive: it subscribes to live state topics and
does not publish control/configuration messages.

Optional MQTT credential paths under Home Assistant config:

- `/config/bcone_mqtt_auth/AmazonRootCA1.pem`
- `/config/bcone_mqtt_auth/client.crt`
- `/config/bcone_mqtt_auth/private.key`

If any of those files are missing, the integration stays REST-only and the
`MQTT Connected` entity remains off.

## Safety

Do not commit account data, tokens, private device IDs, raw captures, payload
values, MQTT configs, or PEM files.
