"""Optional passive BCone MQTT listener."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path
import secrets
import ssl
import time
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    BCONE_MQTT_AUTH_DIR,
    BCONE_MQTT_CA_FILE,
    BCONE_MQTT_CERT_FILE,
    BCONE_MQTT_ENDPOINT,
    BCONE_MQTT_KEY_FILE,
    BCONE_MQTT_PORT,
)

_KEEPALIVE_SECONDS = 60
_RECONNECT_SECONDS = 30


@dataclass(frozen=True, slots=True)
class BconeMqttCredentials:
    """Local file paths for optional BCone MQTT mTLS credentials."""

    ca_file: Path
    cert_file: Path
    key_file: Path

    @classmethod
    def from_hass(cls, hass: HomeAssistant) -> "BconeMqttCredentials":
        """Return default credential paths under Home Assistant config."""

        base = Path(hass.config.path(BCONE_MQTT_AUTH_DIR))
        return cls(
            ca_file=base / BCONE_MQTT_CA_FILE,
            cert_file=base / BCONE_MQTT_CERT_FILE,
            key_file=base / BCONE_MQTT_KEY_FILE,
        )

    @property
    def available(self) -> bool:
        """Return true when all required MQTT credential files exist."""

        return self.ca_file.is_file() and self.cert_file.is_file() and self.key_file.is_file()


class BconeMqttListener:
    """Read-only MQTT listener for BCone live indication payloads."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        device_id: str,
        credentials: BconeMqttCredentials,
        status_callback: Callable[[bool, str | None], None],
        payload_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        self._hass = hass
        self._device_id = device_id
        self._credentials = credentials
        self._status_callback = status_callback
        self._payload_callback = payload_callback
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    @property
    def topics(self) -> tuple[str, ...]:
        """Return the subscribed MQTT topics."""

        return ("FW", f"bc/{self._device_id}/ind", f"bc/{self._device_id}/updatefwstat")

    def start(self) -> None:
        """Start the background MQTT listener task."""

        if self._task is None:
            self._task = self._hass.loop.create_task(self._run_forever())

    async def stop(self) -> None:
        """Stop the background MQTT listener task."""

        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass

    async def _run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - listener reports sanitized connection state.
                self._status_callback(False, exc.__class__.__name__)

            if not self._stop_event.is_set():
                await asyncio.sleep(_RECONNECT_SECONDS)

    async def _connect_and_listen(self) -> None:
        context = await self._hass.async_add_executor_job(_create_ssl_context, self._credentials)
        client_id = _client_id()
        reader: asyncio.StreamReader | None = None
        writer: asyncio.StreamWriter | None = None
        try:
            reader, writer = await asyncio.open_connection(
                BCONE_MQTT_ENDPOINT,
                BCONE_MQTT_PORT,
                ssl=context,
                server_hostname=BCONE_MQTT_ENDPOINT,
            )
            writer.write(_connect_packet(client_id, keepalive=_KEEPALIVE_SECONDS))
            await writer.drain()
            connack = await _read_packet(reader)
            if len(connack) < 4 or connack[0] != 0x20 or connack[3] != 0:
                raise BconeMqttError("MQTT CONNACK did not accept the connection")

            writer.write(_subscribe_packet(1, list(self.topics)))
            await writer.drain()
            suback = await _read_packet(reader)
            if not _suback_success(suback, len(self.topics)):
                raise BconeMqttError("MQTT SUBACK did not grant all subscriptions")

            self._status_callback(True, None)
            while not self._stop_event.is_set():
                try:
                    packet = await asyncio.wait_for(_read_packet(reader), timeout=_KEEPALIVE_SECONDS / 2)
                except TimeoutError:
                    writer.write(b"\xC0\x00")
                    await writer.drain()
                    continue

                packet_type = packet[0] >> 4 if packet else 0
                if packet_type == 13:
                    continue
                if packet_type == 3:
                    self._handle_publish(packet)
        finally:
            self._status_callback(False, None)
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except (ConnectionError, ssl.SSLError):
                    pass
            _ = reader

    def _handle_publish(self, packet: bytes) -> None:
        parsed = _parse_publish_packet(packet)
        if parsed is None or parsed["topic"] != f"bc/{self._device_id}/ind":
            return
        try:
            payload = json.loads(parsed["payload"].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if isinstance(payload, dict):
            self._payload_callback(payload)


class BconeMqttError(Exception):
    """Sanitized MQTT listener error."""


def _create_ssl_context(credentials: BconeMqttCredentials) -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=str(credentials.ca_file))
    context.load_cert_chain(certfile=str(credentials.cert_file), keyfile=str(credentials.key_file))
    return context


def _client_id() -> str:
    return f"{int(time.time() * 1000)}_{secrets.randbelow(100000000):08d}"


async def _read_packet(reader: asyncio.StreamReader) -> bytes:
    header = bytearray(await reader.readexactly(1))
    multiplier = 1
    remaining = 0
    while True:
        digit = (await reader.readexactly(1))[0]
        header.append(digit)
        remaining += (digit & 0x7F) * multiplier
        if (digit & 0x80) == 0:
            break
        multiplier *= 128
    body = await reader.readexactly(remaining)
    return bytes(header + body)


def _connect_packet(client_id: str, *, keepalive: int) -> bytes:
    variable_header = _utf8("MQTT") + bytes([0x04, 0x02]) + keepalive.to_bytes(2, "big")
    payload = _utf8(client_id)
    body = variable_header + payload
    return bytes([0x10]) + _remaining_length(len(body)) + body


def _subscribe_packet(packet_id: int, topics: list[str]) -> bytes:
    variable_header = packet_id.to_bytes(2, "big")
    payload = b"".join(_utf8(topic) + bytes([0x00]) for topic in topics)
    body = variable_header + payload
    return bytes([0x82]) + _remaining_length(len(body)) + body


def _suback_success(packet: bytes, subscription_count: int) -> bool:
    return (
        len(packet) >= 5
        and packet[0] == 0x90
        and len(packet[4:]) == subscription_count
        and all(code in {0, 1, 2} for code in packet[4:])
    )


def _parse_publish_packet(packet: bytes) -> dict[str, Any] | None:
    if not packet or packet[0] >> 4 != 3:
        return None
    try:
        remaining_length, offset = _decode_remaining_length(packet, 1)
    except ValueError:
        return None
    end = offset + remaining_length
    if end > len(packet) or offset + 2 > len(packet):
        return None
    topic_len = int.from_bytes(packet[offset : offset + 2], "big")
    topic_start = offset + 2
    topic_end = topic_start + topic_len
    if topic_end > end:
        return None
    qos = (packet[0] >> 1) & 0x03
    payload_start = topic_end + (2 if qos else 0)
    if payload_start > end:
        return None
    try:
        topic = packet[topic_start:topic_end].decode("utf-8")
    except UnicodeDecodeError:
        return None
    return {"topic": topic, "qos": qos, "payload": packet[payload_start:end]}


def _decode_remaining_length(packet: bytes, offset: int) -> tuple[int, int]:
    multiplier = 1
    value = 0
    while True:
        if offset >= len(packet):
            raise ValueError("truncated MQTT remaining length")
        digit = packet[offset]
        offset += 1
        value += (digit & 0x7F) * multiplier
        if (digit & 0x80) == 0:
            return value, offset
        multiplier *= 128


def _utf8(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return len(encoded).to_bytes(2, "big") + encoded


def _remaining_length(value: int) -> bytes:
    encoded = bytearray()
    while True:
        digit = value % 128
        value //= 128
        if value:
            digit |= 0x80
        encoded.append(digit)
        if not value:
            return bytes(encoded)
