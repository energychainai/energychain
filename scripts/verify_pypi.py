"""Verify an unpinned install from official PyPI against the exact release artifacts."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import venv

from check_dist import check_distributions


def verify(dist: Path, retries: int) -> None:
    artifacts = check_distributions(dist, require_license=True)
    version = artifacts["version"]
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(
                    f"https://pypi.org/pypi/energychain/{version}/json", timeout=30) as response:
                release = json.load(response)
            published = {p["filename"]: p for p in release["urls"]}
            if not set(artifacts["sha256"]).issubset(published):
                raise ValueError("release files have not all appeared on PyPI")
            break
        except (urllib.error.URLError, ValueError):
            if attempt + 1 == retries:
                raise
            time.sleep(10)
    for name, digest in artifacts["sha256"].items():
        if published[name]["yanked"] or published[name]["digests"]["sha256"] != digest:
            raise ValueError(f"PyPI file differs from the tested release: {name}")
    with tempfile.TemporaryDirectory(prefix="energychain-pypi-") as directory:
        root = Path(directory)
        venv.EnvBuilder(with_pip=True).create(root / "venv")
        python = root / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("PIP_") and k not in {"PYTHONPATH", "PYTHONHOME"}}
        env["PIP_CONFIG_FILE"] = os.devnull
        report = root / "pip-report.json"
        subprocess.run([
            str(python), "-I", "-m", "pip", "install", "--index-url", "https://pypi.org/simple/",
            "--no-cache-dir", "--only-binary=:all:", "--report", str(report), "energychain",
        ], cwd=root, env=env, check=True)
        package = next(p for p in json.loads(report.read_text())["install"]
                       if p["metadata"]["name"] == "energychain")
        if package["metadata"]["version"] != version:
            raise ValueError("unpinned pip install selected a different version")
        download = package["download_info"]
        if not download["url"].startswith("https://files.pythonhosted.org/"):
            raise ValueError("pip did not download from the official PyPI file host")
        wheel = next(n for n in artifacts["sha256"] if n.endswith(".whl"))
        if download["archive_info"]["hashes"]["sha256"] != artifacts["sha256"][wheel]:
            raise ValueError("installed wheel hash does not match the tested artifact")
        subprocess.run([str(python), "-I", "-m", "pip", "check"], cwd=root, env=env, check=True)
        subprocess.run([str(python), "-I", str(Path(__file__).with_name("smoke_test.py"))],
                       cwd=root, env=env, check=True)
    print(f"Verified pip install energychain: {version}, official PyPI, matching SHA256.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--retries", type=int, default=12)
    args = parser.parse_args()
    if args.retries < 1:
        parser.error("--retries must be positive")
    verify(args.dist, args.retries)
