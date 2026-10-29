#!/usr/bin/env python3
"""Flag common sensitive files and credential patterns before a public release.

This is a conservative guardrail, not a substitute for review or a mature scanner.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"),
    "OpenAI key": re.compile(rb"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(rb"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b"),
    "GitHub fine-grained token": re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{30,}\b"),
    "AWS access key": re.compile(rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "Google API key": re.compile(rb"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "Slack token": re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{15,}\b"),
    "Stripe secret key": re.compile(rb"\bsk_(?:live|test)_[A-Za-z0-9]{20,}\b"),
}


def matches(data: bytes) -> list[str]:
    """Return signature names only, never the secret values themselves."""
    return [name for name, expression in PATTERNS.items() if expression.search(data)]


def unsafe_path(filename: str) -> bool:
    path = Path(filename)
    name = path.name.lower()
    if name == ".env" or name.startswith(".env.") or name in {"credentials.json", "secrets.json", "id_rsa", "id_ed25519"}:
        return True
    if path.suffix.lower() in {".pem", ".p12", ".pfx", ".key", ".sqlite", ".sqlite3", ".db"}:
        return True
    return False


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.DEVNULL)


def scan_tracked_files() -> list[str]:
    warnings: list[str] = []
    paths = git("ls-files", "-z").split(b"\0")
    for encoded in paths:
        if not encoded:
            continue
        name = encoded.decode("utf-8", errors="replace")
        if unsafe_path(name):
            warnings.append(f"{name}: unsafe tracked filename")
            continue
        data = (ROOT / name).read_bytes()
        for kind in matches(data):
            warnings.append(f"{name}: possible {kind}")
    return warnings


def scan_history() -> list[str]:
    # A full clone is necessary; CI checks out all history before this runs.
    warnings: list[str] = []
    history = git("log", "--all", "--format=", "--patch", "--no-ext-diff", "--no-renames")
    for kind in matches(history):
        warnings.append(f"Git history: possible {kind}")
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true", help="Also scan accessible local Git patch history")
    arguments = parser.parse_args()
    try:
        findings = scan_tracked_files()
        if arguments.history:
            findings.extend(scan_history())
    except (subprocess.CalledProcessError, OSError) as error:
        print(f"Could not finish repository audit: {error}", file=sys.stderr)
        return 2
    if findings:
        for finding in findings:
            print(f"Sensitive-content review required: {finding}", file=sys.stderr)
        return 1
    print("No common credential patterns detected; manual review is still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
