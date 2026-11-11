import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "release.py"
spec = importlib.util.spec_from_file_location("release", SCRIPT)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)

CHANGELOG = """# Changelog

## [Unreleased]

### Added

- New thing.

## [0.1.0] - 2026-01-01

- First release.
"""


@pytest.mark.parametrize(
    ("part", "expected"),
    [("patch", "1.2.4"), ("minor", "1.3.0"), ("major", "2.0.0"), ("3.0.1", "3.0.1")],
)
def test_bump(part, expected):
    assert release.bump("1.2.3", part) == expected


def test_bump_rejects_garbage():
    with pytest.raises(release.ReleaseError):
        release.bump("1.2.3", "big")


def test_roll_changelog_moves_unreleased_into_a_dated_section():
    rolled = release.roll_changelog(CHANGELOG, "0.2.0", "2026-02-02")
    assert "## [Unreleased]\n\n## [0.2.0] - 2026-02-02\n\n### Added\n\n- New thing." in rolled
    assert "## [0.1.0] - 2026-01-01" in rolled
    assert release.changelog_section(rolled, "0.2.0").endswith("- New thing.")


def test_roll_changelog_needs_entries():
    empty = CHANGELOG.replace("### Added\n\n- New thing.\n", "")
    with pytest.raises(release.ReleaseError, match="nothing under"):
        release.roll_changelog(empty, "0.2.0", "2026-02-02")


def test_changelog_section_missing_version():
    with pytest.raises(release.ReleaseError, match="no entries for 9.9.9"):
        release.changelog_section(CHANGELOG, "9.9.9")


def test_check_requires_tag_pyproject_and_changelog_to_agree(tmp_path, monkeypatch):
    pyproject, changelog = tmp_path / "pyproject.toml", tmp_path / "CHANGELOG.md"
    pyproject.write_text('[project]\nversion = "0.1.0"\n')
    changelog.write_text(CHANGELOG)
    monkeypatch.setattr(release, "PYPROJECT", pyproject)
    monkeypatch.setattr(release, "CHANGELOG", changelog)

    assert release.main(["check", "v0.1.0"]) == 0
    assert release.main(["check", "v0.2.0"]) == 1
    assert release.main(["check", "0.1"]) == 1
    pyproject.write_text('[project]\nversion = "0.3.0"\n')
    assert release.main(["check", "v0.3.0"]) == 1
