"""Check release artifacts without importing the working tree or contacting an index."""
from __future__ import annotations

import argparse
import ast
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import tarfile
import zipfile


def check_distributions(dist: Path, *, tag: str | None = None,
                        require_license: bool = False) -> dict:
    wheels = list(dist.glob("*.whl"))
    sdists = list(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1 or len(list(dist.iterdir())) != 2:
        raise ValueError("dist must contain exactly one wheel and one source distribution")
    with zipfile.ZipFile(wheels[0]) as wheel:
        names = wheel.namelist()
        metadata_name = next(n for n in names if n.endswith(".dist-info/METADATA"))
        metadata = BytesParser().parsebytes(wheel.read(metadata_name))
        init = ast.parse(wheel.read("energychain/__init__.py"))
        source_version = next(
            ast.literal_eval(n.value) for n in init.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "__version__" for t in n.targets))
        version = metadata["Version"]
        if metadata["Name"] != "energychain" or version != source_version:
            raise ValueError("distribution name/version does not match the SDK")
        if wheels[0].name != f"energychain-{version}-py3-none-any.whl":
            raise ValueError("unexpected wheel name or compatibility tag")
        if metadata["Requires-Python"] != ">=3.10":
            raise ValueError("unexpected Python compatibility metadata")
        if tag is not None and tag != f"v{version}":
            raise ValueError(f"release tag must be v{version}; received {tag!r}")
        if any("extra ==" not in r for r in metadata.get_all("Requires-Dist", [])):
            raise ValueError("core package must remain free of runtime dependencies")
        license_terms = metadata["License-Expression"] or metadata["License"]
        license_names = metadata.get_all("License-File", [])
        if require_license:
            if not license_terms or not license_names:
                raise ValueError("owner-approved license metadata and LICENSE file are required")
            license_payloads = [
                wheel.read(n) for n in names
                if any(n.endswith("/" + f) for f in license_names)]
            if not license_payloads or not all(p.strip() for p in license_payloads):
                raise ValueError("wheel is missing the selected licensing terms")
        sdk_files = {n: wheel.read(n) for n in names if n.startswith("energychain/")}
    with tarfile.open(sdists[0], "r:gz") as sdist:
        prefix = f"energychain-{version}/"
        pkg_info = sdist.extractfile(prefix + "PKG-INFO")
        if pkg_info is None:
            raise ValueError("source distribution has no PKG-INFO")
        source_metadata = BytesParser().parsebytes(pkg_info.read())
        if any(source_metadata[key] != metadata[key] for key in (
                "Name", "Version", "Requires-Python", "License-Expression", "License")):
            raise ValueError("wheel and source metadata differ")
        source_names = {n.name for n in sdist.getmembers()}
        if sdists[0].name != f"energychain-{version}.tar.gz":
            raise ValueError("unexpected source distribution name")
        for name, contents in sdk_files.items():
            member = sdist.extractfile(prefix + "src/" + name)
            if member is None or member.read() != contents:
                raise ValueError(f"wheel/source SDK content differs: {name}")
        if require_license and any(prefix + f not in source_names for f in license_names):
            raise ValueError("source distribution is missing licensing terms")
    return {
        "name": "energychain", "version": version,
        "license_selected": bool(license_terms and license_names),
        "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(wheels + sdists)},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--tag")
    parser.add_argument("--require-license", action="store_true")
    args = parser.parse_args()
    try:
        result = check_distributions(
            args.dist, tag=args.tag, require_license=args.require_license)
    except (ValueError, KeyError, StopIteration) as exc:
        parser.exit(1, f"Release blocked: {exc}\n")
    print(json.dumps(result, indent=2))
