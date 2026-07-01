# BCone Home Assistant Integration

Production workspace for a HACS-installable Home Assistant integration for
BCone.

Initial target: read-only MQTT monitoring using the mapped BCone AWS IoT
connection and decoded `/ind` state payloads. Control, configuration writes,
and firmware actions are out of scope until they are separately proved and
reviewed.

## Status

This repository is being initialized from the BCone research workspace. The
first production milestone is a read-only custom integration with:

- local MQTT mTLS configuration
- passive subscribe/listen behavior only
- decoded hub and pool-unit state entities
- redacted diagnostics
- no Home Assistant services and no MQTT publish calls

## Safety

Do not commit private MQTT configs, PEM files, captures, device IDs, account
data, or raw payload values.
