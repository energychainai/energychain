"""HMAC-bound, expiring and one-time approvals for security-sensitive tool execution.

Approval issuance must occur in a separate, trusted application service after a real human
approval. Keeping this issuer in the same untrusted client process is NOT production security.
"""
from __future__ import annotations
from datetime import datetime
import base64
import hashlib
import hmac
import json
import secrets
from threading import Lock
from typing import Any, Callable
from energychain.exceptions import ApprovalRequired, ValidationError
from energychain.models import utcnow
from energychain.security import Principal


def canonical_parameters(value: dict[str, Any] | None) -> str:
    try:
        return json.dumps(value or {}, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValidationError("action parameters must be canonical JSON values") from exc


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


class SignedApprovalAuthority:
    """Process-local replay protection; use shared atomic nonce storage across workers."""
    def __init__(self, secret: bytes, *, clock: Callable[[], datetime] = utcnow) -> None:
        if len(secret) < 32:
            raise ValidationError("approval signing secret must be at least 32 bytes")
        self._key = secret
        self._clock = clock
        self._consumed: set[str] = set()
        self._lock = Lock()

    def issue(self, principal: Principal, site_id: str, action: str,
              parameters: dict | None = None, *, expires_in: int = 120) -> str:
        """Trusted issuer ONLY: never expose this method as a public unauthenticated endpoint."""
        if not 1 <= expires_in <= 900:
            raise ValidationError("approval validity must be 1..900 seconds")
        now = self._clock()
        payload = {"v": 1, "who": principal.id, "site": site_id, "action": action,
                   "params_sha256": hashlib.sha256(canonical_parameters(parameters).encode()).hexdigest(),
                   "expires": int(now.timestamp()) + expires_in,
                   "nonce": secrets.token_hex(16)}
        body = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        mac = _b64(hmac.new(self._key, body.encode(), hashlib.sha256).digest())
        return body + "." + mac

    def verify_and_consume(self, token: str, principal: Principal, site_id: str,
                           action: str, parameters: dict | None = None) -> None:
        try:
            encoded, mac = token.split(".", 1)
            expected = _b64(hmac.new(self._key, encoded.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(expected, mac):
                raise ApprovalRequired("approval verification failed")
            data = json.loads(_unb64(encoded))
            digest = hashlib.sha256(canonical_parameters(parameters).encode()).hexdigest()
            if (data.get("v") != 1 or data.get("who") != principal.id or
                data.get("site") != site_id or data.get("action") != action or
                not hmac.compare_digest(str(data.get("params_sha256", "")), digest) or
                data.get("expires", -1) < int(self._clock().timestamp())):
                raise ApprovalRequired("approval scope or expiry mismatch")
            nonce = data["nonce"]
            if not isinstance(nonce, str) or len(nonce) != 32:
                raise ApprovalRequired("invalid approval nonce")
            with self._lock:
                if nonce in self._consumed:
                    raise ApprovalRequired("approval already consumed")
                self._consumed.add(nonce)
        except (ValueError, TypeError, KeyError, UnicodeError) as exc:
            raise ApprovalRequired("malformed approval") from exc
