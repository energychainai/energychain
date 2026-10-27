"""Minimal defensive JSON GET transport for opted-in external services.

Configured hostnames are not accepted from model output; redirects are disabled, payloads are
bounded, and authentication information is never included in exception messages.
"""
from __future__ import annotations
import json
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from energychain.exceptions import ValidationError, ToolError


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ToolError("third-party HTTP redirect refused")


def get_json(url: str, *, token: str | None = None, timeout: float = 8,
             max_response_bytes: int = 1_048_576) -> object:
    u = urlsplit(url)
    if u.scheme != "https" or not u.hostname or u.username or u.password:
        raise ValidationError("external API transport requires HTTPS hostname and no URL credentials")
    if not 0 < timeout <= 60 or not 0 < max_response_bytes <= 4_194_304:
        raise ValidationError("invalid transport limits")
    headers = {"Accept": "application/json", "User-Agent": "EnergyChain/0.1"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        with build_opener(_RejectRedirects()).open(Request(url, headers=headers), timeout=timeout) as response:
            if response.status != 200:
                raise ToolError(f"data provider returned HTTP {response.status}")
            blob = response.read(max_response_bytes + 1)
            if len(blob) > max_response_bytes:
                raise ToolError("data provider response exceeds size limit")
            return json.loads(blob.decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        # Do not leak URLs with query params, access tokens, or provider response bodies.
        raise ToolError(f"external data request failed: {type(exc).__name__}") from exc
