#!/usr/bin/env python3
"""Release helper, also used by the release workflow.

python scripts/release.py prepare patch|minor|major|X.Y.Z [--push] [--dry-run]
python scripts/release.py check vX.Y.Z    # tag, pyproject.toml and changelog agree
python scripts/release.py notes vX.Y.Z    # print the changelog section for the release
"""

import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"
VERSION_LINE = re.compile(r'^version = "([^"]+)"$', re.MULTILINE)
SEMVER = re.compile(r"\d+\.\d+\.\d+")
CHECKS = (
    ["ruff", "format", "--check", "."],
    ["ruff", "check", "."],
    ["pytest", "-q"],
)


class ReleaseError(Exception):
    """Raised when a release cannot be prepared or verified."""


def read_version(text):
    match = VERSION_LINE.search(text)
    if not match:
        raise ReleaseError("No version found in pyproject.toml.")
    return match.group(1)


def bump(version, part):
    """Return the next version for major/minor/patch, or an explicit X.Y.Z."""
    major, minor, patch = (int(number) for number in version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if SEMVER.fullmatch(part):
        return part
    raise ReleaseError(f"Expected major, minor, patch or X.Y.Z, got: {part}")


def changelog_section(text, version):
    """Return the body of the '## [version]' section; raise when missing or empty."""
    pattern = rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    body = match.group(1).strip() if match else ""
    if not body:
        raise ReleaseError(f"CHANGELOG.md has no entries for {version}.")
    return body


def roll_changelog(text, version, today):
    """Turn [Unreleased] into a dated release section and start a fresh [Unreleased]."""
    match = re.search(
        r"^## \[Unreleased\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.MULTILINE | re.DOTALL
    )
    if not match or not match.group(1).strip():
        raise ReleaseError("CHANGELOG.md has nothing under [Unreleased].")
    section = f"## [Unreleased]\n\n## [{version}] - {today}\n\n{match.group(1).strip()}\n\n"
    return (text[: match.start()] + section + text[match.end() :]).rstrip() + "\n"


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def prepare(args):
    pyproject = PYPROJECT.read_text()
    version = bump(read_version(pyproject), args.version)
    tag = f"v{version}"
    if git("status", "--porcelain"):
        raise ReleaseError("Working tree is not clean.")
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        raise ReleaseError("Releases are made from main.")
    if git("tag", "--list", tag):
        raise ReleaseError(f"Tag {tag} already exists.")
    changelog = roll_changelog(CHANGELOG.read_text(), version, datetime.date.today().isoformat())

    print(f"Releasing {tag}:\n\n{changelog_section(changelog, version)}\n")
    if args.dry_run:
        return
    for check in CHECKS:
        subprocess.run([sys.executable, "-m", *check], cwd=ROOT, check=True)

    PYPROJECT.write_text(VERSION_LINE.sub(f'version = "{version}"', pyproject, count=1))
    CHANGELOG.write_text(changelog)
    git("add", "pyproject.toml", "CHANGELOG.md")
    git("commit", "-m", f"release {tag}")
    git("tag", "-a", tag, "-m", tag)
    if args.push:
        git("push", "origin", "main", tag)
        print(f"Pushed {tag}; the release workflow takes over.")
    else:
        print(f"Created commit and tag {tag}. Publish with: git push origin main {tag}")


def check(args):
    version = args.tag.removeprefix("v")
    if not SEMVER.fullmatch(version):
        raise ReleaseError(f"Tag must look like vX.Y.Z, got: {args.tag}")
    declared = read_version(PYPROJECT.read_text())
    if declared != version:
        raise ReleaseError(f"Tag is {version} but pyproject.toml says {declared}.")
    changelog_section(CHANGELOG.read_text(), version)
    print(f"{args.tag}: pyproject.toml and CHANGELOG.md agree")


def notes(args):
    print(changelog_section(CHANGELOG.read_text(), args.tag.removeprefix("v")))


def build_parser():
    parser = argparse.ArgumentParser(description="Release helper.")
    commands = parser.add_subparsers(dest="command", required=True)

    prepare_parser = commands.add_parser("prepare", help="bump, roll the changelog, commit, tag")
    prepare_parser.add_argument("version", help="major, minor, patch or an explicit X.Y.Z")
    prepare_parser.add_argument("--push", action="store_true", help="push main and the tag")
    prepare_parser.add_argument("--dry-run", action="store_true", help="only show the release")
    prepare_parser.set_defaults(run=prepare)

    check_parser = commands.add_parser("check", help="verify tag, pyproject.toml and changelog")
    check_parser.add_argument("tag")
    check_parser.set_defaults(run=check)

    notes_parser = commands.add_parser("notes", help="print the changelog section of a tag")
    notes_parser.add_argument("tag")
    notes_parser.set_defaults(run=notes)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.run(args)
    except ReleaseError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as err:
        print(f"error: command failed: {' '.join(map(str, err.cmd))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
