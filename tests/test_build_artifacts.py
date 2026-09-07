import hashlib
import json
from zipfile import ZipFile

import pytest

from scripts.build_artifacts import PACKAGES, prepare_release


def make_wheels(directory, *, mismatched=False):
    for name in sorted(PACKAGES):
        version = "1.0.0.dev1+abc" if not mismatched or name != "fastmcp" else "2.0.0"
        distribution = name.replace("-", "_")
        wheel = directory / f"{distribution}-{version}-py3-none-any.whl"
        with ZipFile(wheel, "w") as archive:
            archive.writestr(
                f"{distribution}-{version}.dist-info/METADATA",
                f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
            )
    (directory / "constraints.txt").write_text("httpx==0.28.1\n")


def test_release_bundle_pins_all_fork_wheels_and_checksums(tmp_path):
    make_wheels(tmp_path)
    assert prepare_release(tmp_path, "abc") == "1.0.0.dev1+abc"
    requirements = (tmp_path / "requirements.txt").read_text().splitlines()
    assert len(requirements) == 5
    assert requirements[0].endswith("/build-latest/constraints.txt")
    assert all("PureCipher/xsecuremcp2.0/" in line for line in requirements)
    assert all("#sha256=" in line and "%2Babc" in line for line in requirements[1:])
    assert json.loads((tmp_path / "build.json").read_text())["commit"] == "abc"
    with ZipFile(tmp_path / "xsecuremcp2.0-python.zip") as archive:
        assert len([name for name in archive.namelist() if name.endswith(".whl")]) == 4
        assert "constraints.txt" in archive.namelist()
    for line in (tmp_path / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize(
    "problem", ["missing-wheel", "different-versions", "missing-constraints"]
)
def test_release_refuses_incomplete_or_inconsistent_packages(tmp_path, problem):
    make_wheels(tmp_path, mismatched=problem == "different-versions")
    if problem == "missing-wheel":
        next(tmp_path.glob("*.whl")).unlink()
    if problem == "missing-constraints":
        (tmp_path / "constraints.txt").unlink()
    with pytest.raises(ValueError):
        prepare_release(tmp_path, "abc")
