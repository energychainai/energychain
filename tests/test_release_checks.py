"""The release gate must reject inconsistent or unlicensed distribution artifacts."""
import io
from pathlib import Path
import runpy
import tarfile
import zipfile

import pytest

check_distributions = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts" / "check_dist.py")
)["check_distributions"]


def make_distributions(path, *, source_version="0.1.0", licensed=False):
    path.mkdir()
    metadata = b"Metadata-Version: 2.4\nName: energychain\nVersion: 0.1.0\nRequires-Python: >=3.10\n"
    if licensed:
        metadata += b"License-Expression: MIT\nLicense-File: LICENSE\n"
    sdk = b'__version__ = "0.1.0"\n'
    with zipfile.ZipFile(path / "energychain-0.1.0-py3-none-any.whl", "w") as wheel:
        wheel.writestr("energychain/__init__.py", sdk)
        wheel.writestr("energychain-0.1.0.dist-info/METADATA", metadata)
        if licensed:
            wheel.writestr("energychain-0.1.0.dist-info/licenses/LICENSE", b"test fixture only")
    with tarfile.open(path / "energychain-0.1.0.tar.gz", "w:gz") as sdist:
        files = {
            "PKG-INFO": metadata,
            "src/energychain/__init__.py": f'__version__ = "{source_version}"\n'.encode(),
        }
        if licensed:
            files["LICENSE"] = b"test fixture only"
        for name, data in files.items():
            member = tarfile.TarInfo("energychain-0.1.0/" + name)
            member.size = len(data)
            sdist.addfile(member, io.BytesIO(data))
    return path


def test_technical_check_reports_missing_license(tmp_path):
    result = check_distributions(make_distributions(tmp_path / "dist"), tag="v0.1.0")
    assert result["version"] == "0.1.0"
    assert not result["license_selected"]
    assert len(result["sha256"]) == 2


def test_public_release_rejects_missing_license(tmp_path):
    with pytest.raises(ValueError, match="license metadata"):
        check_distributions(make_distributions(tmp_path / "dist"), require_license=True)


def test_public_release_checks_license_in_both_archives(tmp_path):
    result = check_distributions(
        make_distributions(tmp_path / "dist", licensed=True), require_license=True)
    assert result["license_selected"]


def test_release_tag_must_match_package_version(tmp_path):
    with pytest.raises(ValueError, match="release tag"):
        check_distributions(make_distributions(tmp_path / "dist"), tag="v0.2.0")


def test_source_and_wheel_cannot_disagree(tmp_path):
    with pytest.raises(ValueError, match="content differs"):
        check_distributions(make_distributions(tmp_path / "dist", source_version="9.9.9"))


def test_extra_release_files_are_rejected(tmp_path):
    dist = make_distributions(tmp_path / "dist")
    (dist / "unreviewed.txt").write_text("not a package")
    with pytest.raises(ValueError, match="exactly one wheel"):
        check_distributions(dist)
