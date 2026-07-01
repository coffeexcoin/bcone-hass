"""Constants for the BCone integration."""

from __future__ import annotations

DOMAIN = "bcone"
PLATFORMS = ["binary_sensor", "sensor"]

CONF_EMAIL = "email"
CONF_MOBILE_DEVICE_ID = "mobile_device_id"
CONF_DEVICE_ID = "device_id"
CONF_NAME = "name"
CONF_TOKENS = "tokens"

DEFAULT_NAME = "BCone"

COGNITO_REGION = "us-east-2"
COGNITO_USER_POOL_ID = "us-east-2_uggOlxx7V"
COGNITO_CLIENT_ID = "4bpqbgr3c49f4v4nfu0ivi2fj6"
COGNITO_IDENTITY_POOL_ID = "us-east-2:d53c79d6-85af-4b03-8a5d-7bf7907c03f9"

BCONE_API_BASE = "https://bcone-server.herokuapp.com/api"
BCONE_MQTT_ENDPOINT = "amlt1z1qj0jvs-ats.iot.us-east-2.amazonaws.com"
BCONE_MQTT_PORT = 8883
BCONE_MQTT_AUTH_DIR = "bcone_mqtt_auth"
BCONE_MQTT_CA_FILE = "AmazonRootCA1.pem"
BCONE_MQTT_CERT_FILE = "client.crt"
BCONE_MQTT_KEY_FILE = "private.key"
