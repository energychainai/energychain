"""Explicitly opted-in, privacy-minimized SDK usage signal for EnergyChain.

This example is NOT imported or executed by the SDK. It has no background
telemetry. You must invoke it yourself with --opt-in to send an activity ping.
No project files, energy readings, API keys, prompts, or email addresses
are included in the payload.
"""
from __future__ import annotations

import argparse
import json
import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

ENDPOINT = "https://energychain.app/api/sdk-telemetry"


def instance_file() -> Path:
    home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return home / "energychain" / "opt-in-instance-id"


def instance_id() -> str:
    path = instance_file()
    if path.exists():
        return str(UUID(path.read_text(encoding="utf-8").strip()))
    new_id = str(uuid4())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_id + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass  # On platforms without POSIX permissions.
    return new_id


def report_opt_in_activity(*, consent: bool = False) -> dict:
    """Send one voluntary usage signal. Never invoked automatically."""
    if not consent:
        raise ValueError("Explicit consent=True is required")
    try:
        sdk_version = version("energychain")
    except PackageNotFoundError as exc:
        raise RuntimeError("Install EnergyChain first: pip install energychain") from exc
    payload = {
        "event": "opt_in_sdk_active",
        "consent": True,
        "instance_id": instance_id(),
        "sdk_version": sdk_version,
    }
    request = Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError) as exc:
        raise RuntimeError("EnergyChain usage signal could not be delivered") from exc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send an OPTIONAL EnergyChain SDK activity ping.")
    parser.add_argument("--opt-in", action="store_true", help="Explicitly consent to this one activity ping.")
    args = parser.parse_args()
    if not args.opt_in:
        parser.error("No data sent. Add --opt-in to submit a voluntary anonymous signal.")
    print(report_opt_in_activity(consent=True))
