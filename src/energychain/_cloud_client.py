"""Opt-in client for the EnergyChain Cloud developer API."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import time
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

CLOUD_ORIGIN = "https://cloud.energychain.app"
STAGING_ORIGIN = "https://staging.energychain.app"
PRODUCTION_CANARY_ORIGIN = (
    "https://ca-ec-production-identity.purplesmoke-259274cf.spaincentral.azurecontainerapps.io"
)
_CLOUD_ORIGINS = frozenset({CLOUD_ORIGIN, STAGING_ORIGIN, PRODUCTION_CANARY_ORIGIN})
_VERIFY_PATH = "/auth/cli/authorize"
_MAX_RESPONSE_BYTES = 1024 * 1024
_DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"
_TOKEN = re.compile(r"ec_cli_[A-Za-z0-9_-]{43}")
_DEVICE_CODE = re.compile(r"[A-Za-z0-9_-]{43}")
_USER_CODE = re.compile(r"[BCDFGHJKLMNPQRSTVWXYZ23456789]{4}-[BCDFGHJKLMNPQRSTVWXYZ23456789]{4}")


class CloudError(Exception):
    """A user-facing Cloud error with no provider payload or credentials."""


def require_cloud_origin(origin: str) -> str:
    if not isinstance(origin, str) or origin not in _CLOUD_ORIGINS:
        raise CloudError("Choose a supported EnergyChain Cloud HTTPS origin.")
    return origin


class CloudHTTPError(CloudError):
    def __init__(self, status: int, error: str | None):
        messages = {
            400: "Cloud could not validate this request.",
            401: "Your Cloud authorization expired or was revoked. Run energychain auth login.",
            403: "Your Cloud identity cannot access that resource.",
            404: "Cloud could not find that resource for your identity.",
            409: "Cloud rejected conflicting workflow or deployment details.",
            413: "The workflow submission exceeds the Cloud size limit.",
            429: "Cloud is receiving requests too quickly. Wait and try again.",
        }
        super().__init__(messages.get(status, "Cloud could not complete this request."))
        self.status = status
        self.error = error


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def canonical_json(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _payload(response) -> dict:
    content = response.read(_MAX_RESPONSE_BYTES + 1)
    if len(content) > _MAX_RESPONSE_BYTES:
        raise CloudError("Cloud returned a response above the size limit.")
    if response.headers.get_content_type() != "application/json":
        raise CloudError("Cloud returned an unexpected response format.")
    try:
        data = json.loads(content)
    except (ValueError, RecursionError):
        raise CloudError("Cloud returned an invalid JSON response.") from None
    if not isinstance(data, dict):
        raise CloudError("Cloud returned an unexpected response.")
    return data


def is_token(value) -> bool:
    return isinstance(value, str) and bool(_TOKEN.fullmatch(value))


class CloudClient:
    """Use the EnergyChain Cloud TLS origin without forwarding bearer tokens."""

    def __init__(self, *, origin: str = CLOUD_ORIGIN, opener=None):
        self._origin = require_cloud_origin(origin)
        self._opener = opener or build_opener(ProxyHandler({}), _NoRedirect())

    def request(self, method: str, path: str, *, token: str | None = None, json_data=None,
                form: dict | None = None) -> dict | None:
        if token is not None and not is_token(token):
            raise CloudError("Stored Cloud authorization is invalid. Run energychain auth login.")
        return self._request(method, path, token=token, json_data=json_data, form=form)

    def _request(self, method: str, path: str, *, token: str | None, json_data=None,
                 form: dict | None = None) -> dict | None:
        if not path.startswith("/v1/") or not path.isascii() or any(c.isspace() for c in path):
            raise ValueError("Invalid Cloud API path.")
        headers = {"Accept": "application/json", "Cache-Control": "no-store"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        body = None
        if json_data is not None:
            headers["Content-Type"] = "application/json"
            body = canonical_json(json_data)
        if form is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            body = urlencode(form).encode("ascii")
        request = Request(self._origin + path, data=body, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=12) as response:
                return None if response.status == 204 else _payload(response)
        except HTTPError as error:
            with error:
                try:
                    error_code = _payload(error).get("error")
                except (CloudError, OSError, HTTPException):
                    error_code = None
                raise CloudHTTPError(error.code, error_code if isinstance(error_code, str) else None) from None
        except (OSError, HTTPException):
            raise CloudError("Could not connect to EnergyChain Cloud.") from None

    def login(self, *, show_code, open_browser, monotonic=time.monotonic, sleep=time.sleep) -> str:
        verifier = secrets.token_urlsafe(32)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        authorization = self.request("POST", "/v1/auth/device", form={
            "code_challenge": challenge.rstrip(b"=").decode("ascii"),
            "code_challenge_method": "S256",
        })
        verification_url = self._origin + _VERIFY_PATH
        if authorization is None or authorization.get("verification_uri") != verification_url:
            raise CloudError("Cloud returned an unexpected authorization page.")
        device_code = authorization.get("device_code")
        user_code = authorization.get("user_code")
        lifetime, interval = authorization.get("expires_in"), authorization.get("interval")
        if (not isinstance(device_code, str) or not _DEVICE_CODE.fullmatch(device_code)
                or not isinstance(user_code, str) or not _USER_CODE.fullmatch(user_code)
                or type(lifetime) is not int or not 1 <= lifetime <= 1800
                or type(interval) is not int or not 1 <= interval <= 60):
            raise CloudError("Cloud returned invalid authorization details.")
        deadline = monotonic() + lifetime
        show_code(verification_url, user_code)
        if open_browser is not None:
            open_browser(verification_url)
        while monotonic() + interval < deadline:
            sleep(interval)
            try:
                credential = self.request("POST", "/v1/auth/token", form={
                    "grant_type": _DEVICE_GRANT,
                    "device_code": device_code,
                    "code_verifier": verifier,
                })
            except CloudHTTPError as error:
                if error.error == "authorization_pending":
                    continue
                if error.error == "slow_down":
                    interval += 5
                    continue
                if error.error in {"expired_token", "invalid_grant", "access_denied"}:
                    raise CloudError("Cloud authorization ended. Run energychain auth login again.") from None
                raise
            expires_in = credential.get("expires_in") if credential else None
            if (credential and credential.get("token_type") == "Bearer"
                    and credential.get("scope") == "cloud:workflow"
                    and type(expires_in) is int and 1 <= expires_in <= 86_400
                    and is_token(credential.get("access_token"))):
                return credential["access_token"]
            raise CloudError("Cloud returned invalid developer authorization.")
        raise CloudError("Cloud authorization expired. Run energychain auth login again.")
