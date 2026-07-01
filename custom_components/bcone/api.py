"""BCone Cognito auth and REST API client."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import BCONE_API_BASE, COGNITO_CLIENT_ID, COGNITO_REGION, COGNITO_USER_POOL_ID

_LOGGER = logging.getLogger(__name__)

_COGNITO_URL = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/"
_COGNITO_TARGET_PREFIX = "AWSCognitoIdentityProviderService"
_INFO_BITS = b"Caldera Derived Key"
_N_HEX = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BCBF6955817183995497CEA956AE515D2261898FA051015"
    "728E5A8AACAA68FFFFFFFFFFFFFFFF"
)
_N = int(_N_HEX, 16)
_G = 2
_K = int(hashlib.sha256(bytes.fromhex("00" + _N_HEX + "0" + f"{_G:x}")).hexdigest(), 16)


class BconeApiError(Exception):
    """Base BCone API error."""


class BconeAuthError(BconeApiError):
    """BCone/Cognito authentication failed."""


class BconeDeviceNotFound(BconeApiError):
    """BCone account did not resolve to a device."""


@dataclass(slots=True)
class BconeTokens:
    """Stored BCone auth tokens."""

    access_token: str
    id_token: str
    refresh_token: str | None
    expires_at: float
    token_type: str = "Bearer"

    @classmethod
    def from_auth_result(cls, result: dict[str, Any], *, refresh_token: str | None = None) -> "BconeTokens":
        """Create tokens from a Cognito AuthenticationResult object."""

        expires_in = int(result.get("ExpiresIn") or 3600)
        return cls(
            access_token=str(result["AccessToken"]),
            id_token=str(result["IdToken"]),
            refresh_token=str(result.get("RefreshToken") or refresh_token) if result.get("RefreshToken") or refresh_token else None,
            expires_at=(datetime.now(UTC) + timedelta(seconds=max(60, expires_in - 60))).timestamp(),
            token_type=str(result.get("TokenType") or "Bearer"),
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BconeTokens":
        """Deserialize stored tokens."""

        return cls(
            access_token=str(value["access_token"]),
            id_token=str(value["id_token"]),
            refresh_token=str(value["refresh_token"]) if value.get("refresh_token") else None,
            expires_at=float(value.get("expires_at") or 0),
            token_type=str(value.get("token_type") or "Bearer"),
        )

    def as_dict(self) -> dict[str, Any]:
        """Serialize tokens for Home Assistant config entry storage."""

        return {
            "access_token": self.access_token,
            "id_token": self.id_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "token_type": self.token_type,
        }

    @property
    def expired(self) -> bool:
        """Return true when access/id tokens should be refreshed."""

        return datetime.now(UTC).timestamp() >= self.expires_at


class BconeApiClient:
    """Small async client for the app-auth and read-only device endpoints."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def authenticate(self, email: str, password: str) -> BconeTokens:
        """Authenticate with Cognito USER_SRP_AUTH."""

        srp = _SrpClient(email=email, password=password)
        try:
            first = await self._cognito(
                "InitiateAuth",
                {
                    "AuthFlow": "USER_SRP_AUTH",
                    "ClientId": COGNITO_CLIENT_ID,
                    "AuthParameters": {"USERNAME": email, "SRP_A": srp.srp_a},
                },
            )
            if first.get("ChallengeName") != "PASSWORD_VERIFIER":
                raise BconeAuthError(f"Unsupported Cognito challenge: {first.get('ChallengeName')}")
            challenge = first.get("ChallengeParameters")
            if not isinstance(challenge, dict):
                raise BconeAuthError("Cognito password verifier challenge was malformed")
            response = await self._cognito(
                "RespondToAuthChallenge",
                {
                    "ChallengeName": "PASSWORD_VERIFIER",
                    "ClientId": COGNITO_CLIENT_ID,
                    "ChallengeResponses": srp.password_verifier_response(challenge),
                },
            )
        except ClientResponseError as exc:
            if exc.status in {400, 401, 403}:
                raise BconeAuthError(str(exc)) from exc
            raise BconeApiError(str(exc)) from exc
        except ClientError as exc:
            raise BconeApiError(str(exc)) from exc

        auth_result = response.get("AuthenticationResult")
        if not isinstance(auth_result, dict):
            raise BconeAuthError("Cognito did not return auth tokens")
        return BconeTokens.from_auth_result(auth_result)

    async def refresh(self, tokens: BconeTokens, *, username: str | None = None) -> BconeTokens:
        """Refresh access/id tokens using the stored refresh token."""

        if not tokens.refresh_token:
            raise BconeAuthError("Missing refresh token")
        auth_parameters = {"REFRESH_TOKEN": tokens.refresh_token}
        if username:
            auth_parameters["USERNAME"] = username
        try:
            response = await self._cognito(
                "InitiateAuth",
                {
                    "AuthFlow": "REFRESH_TOKEN_AUTH",
                    "ClientId": COGNITO_CLIENT_ID,
                    "AuthParameters": auth_parameters,
                },
            )
        except ClientResponseError as exc:
            if exc.status in {400, 401, 403}:
                raise BconeAuthError(str(exc)) from exc
            raise BconeApiError(str(exc)) from exc
        except ClientError as exc:
            raise BconeApiError(str(exc)) from exc

        auth_result = response.get("AuthenticationResult")
        if not isinstance(auth_result, dict):
            raise BconeAuthError("Cognito refresh did not return auth tokens")
        return BconeTokens.from_auth_result(auth_result, refresh_token=tokens.refresh_token)

    async def discover_device_id(self, email: str, mobile_device_id: str, tokens: BconeTokens) -> str:
        """Resolve the BCone device ID for this account/mobile identity."""

        body = {"email": email, "mobileDeviceId": mobile_device_id}
        response = await self._bcone_post("getRelevantDeviceId", body, tokens=tokens)
        device_id = response.get("deviceId")
        if not isinstance(device_id, str) or not device_id:
            raise BconeDeviceNotFound("BCone did not return deviceId")
        return device_id

    async def get_device_history(self, device_id: str, tokens: BconeTokens, *, take: int = 5) -> dict[str, Any]:
        """Read recent device history."""

        return await self._bcone_get(
            "getDeviceHistory",
            tokens=tokens,
            params={"deviceId": device_id, "skip": 0, "take": take},
        )

    async def _cognito(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": f"{_COGNITO_TARGET_PREFIX}.{action}",
        }
        async with self._session.post(_COGNITO_URL, headers=headers, json=payload) as resp:
            if resp.status >= 400:
                text = await resp.text()
                _LOGGER.debug("Cognito %s failed: %s", action, text)
            resp.raise_for_status()
            parsed = await resp.json()
        if not isinstance(parsed, dict):
            raise BconeApiError("Cognito response was not an object")
        return parsed

    async def _bcone_post(self, endpoint: str, body: dict[str, Any], *, tokens: BconeTokens) -> dict[str, Any]:
        async with self._session.post(
            f"{BCONE_API_BASE}/{endpoint}",
            headers=_app_headers(tokens),
            json=body,
        ) as resp:
            if resp.status >= 400:
                text = await resp.text()
                _LOGGER.debug("BCone POST %s failed: %s", endpoint, text)
            resp.raise_for_status()
            parsed = await resp.json()
        if not isinstance(parsed, dict):
            raise BconeApiError(f"BCone POST {endpoint} response was not an object")
        return parsed

    async def _bcone_get(
        self,
        endpoint: str,
        *,
        tokens: BconeTokens,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        async with self._session.get(
            f"{BCONE_API_BASE}/{endpoint}",
            headers=_app_headers(tokens),
            params=params,
        ) as resp:
            if resp.status >= 400:
                text = await resp.text()
                _LOGGER.debug("BCone GET %s failed: %s", endpoint, text)
            resp.raise_for_status()
            parsed = await resp.json()
        if not isinstance(parsed, dict):
            raise BconeApiError(f"BCone GET {endpoint} response was not an object")
        return parsed


class _SrpClient:
    """Cognito SRP math used by AWS USER_SRP_AUTH."""

    def __init__(self, *, email: str, password: str) -> None:
        self.email = email
        self.password = password
        self.small_a = secrets.randbits(256) % _N
        self.large_a = pow(_G, self.small_a, _N)
        if self.large_a % _N == 0:
            raise BconeAuthError("Invalid SRP_A")

    @property
    def srp_a(self) -> str:
        """SRP_A parameter as Cognito expects it."""

        return _pad_hex(self.large_a)

    def password_verifier_response(self, challenge: dict[str, Any]) -> dict[str, str]:
        """Build PASSWORD_VERIFIER challenge responses."""

        user_id_for_srp = str(challenge["USER_ID_FOR_SRP"])
        username = str(challenge.get("USERNAME") or user_id_for_srp)
        salt = int(str(challenge["SALT"]), 16)
        large_b = int(str(challenge["SRP_B"]), 16)
        secret_block = str(challenge["SECRET_BLOCK"])
        if large_b % _N == 0:
            raise BconeAuthError("Invalid SRP_B")

        u_value = int(_hex_hash(_pad_hex(self.large_a) + _pad_hex(large_b)), 16)
        if u_value == 0:
            raise BconeAuthError("Invalid SRP scrambling parameter")

        pool_name = COGNITO_USER_POOL_ID.split("_", maxsplit=1)[1]
        user_password_hash = _text_hash(f"{pool_name}{user_id_for_srp}:{self.password}")
        x_value = int(_hex_hash(_pad_hex(salt) + user_password_hash), 16)
        s_value = pow((large_b - _K * pow(_G, x_value, _N)) % _N, (self.small_a + u_value * x_value) % _N, _N)
        hkdf = _compute_hkdf(bytes.fromhex(_pad_hex(s_value)), bytes.fromhex(_pad_hex(u_value)))
        timestamp = _cognito_timestamp(datetime.now(UTC))
        message = pool_name.encode("utf-8") + user_id_for_srp.encode("utf-8")
        message += base64.b64decode(secret_block) + timestamp.encode("utf-8")
        signature = base64.b64encode(hmac.new(hkdf, message, hashlib.sha256).digest()).decode("utf-8")
        return {
            "USERNAME": username,
            "PASSWORD_CLAIM_SECRET_BLOCK": secret_block,
            "TIMESTAMP": timestamp,
            "PASSWORD_CLAIM_SIGNATURE": signature,
        }


def _app_headers(tokens: BconeTokens) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "App-Version": "2.2.3",
        "Authorization": f"{tokens.token_type} {tokens.id_token}",
        "Content-Type": "application/json",
        "Os-Version": "Home Assistant",
        "Phone-Type": "Home Assistant",
        "User-Agent": "BConeHomeAssistant/0.1",
    }


def _compute_hkdf(ikm: bytes, salt: bytes) -> bytes:
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    info_bits_update = _INFO_BITS + b"\x01"
    return hmac.new(prk, info_bits_update, hashlib.sha256).digest()[:16]


def _hex_hash(value: str) -> str:
    return hashlib.sha256(bytes.fromhex(value)).hexdigest()


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _pad_hex(value: int) -> str:
    value_hex = f"{value:x}"
    if len(value_hex) % 2 == 1:
        value_hex = "0" + value_hex
    elif value_hex[0] in "89abcdefABCDEF":
        value_hex = "00" + value_hex
    return value_hex


def _cognito_timestamp(value: datetime) -> str:
    return f"{value:%a %b} {value.day} {value:%H:%M:%S UTC %Y}"
