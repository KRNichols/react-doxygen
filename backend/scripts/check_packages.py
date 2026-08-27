"""Fail the build when a declared package is not on the repo allowlist."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST = ROOT / "approved-packages.json"
REQ_NAME = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*([<>=!~][^;#]+)?",
)
PY_EXACT = re.compile(r"^==\d+\.\d+\.\d+$")
NODE_EXACT = re.compile(r"^\d+\.\d+\.\d+$")


def is_exact_pin(spec: str, kind: str) -> bool:
    """
    What: True when a specifier is an exact X.Y.Z pin for that ecosystem.
    Why: Ranges and carets must fail the allowlist gate.
    Who: check_exact when it grades declared and allowlist maps.
    Where: Backend ==X.Y.Z pins and frontend X.Y.Z pins.
    How: Match PY_EXACT for python and NODE_EXACT for node after stripping.
    """
    text = (spec or "").strip()
    if kind == "python":
        return bool(PY_EXACT.fullmatch(text))
    return bool(NODE_EXACT.fullmatch(text))


def check_exact(label: str, pins: dict[str, str], kind: str) -> list[str]:
    """
    What: Fail every name whose specifier is not an exact pin.
    Why: >=, ^, and ~ must not sneak past the declared-package gate.
    Who: check_manifests for declared manifests and the allowlist.
    Where: Failure text printed by main and asserted in test_packages.
    How: Walk each name and record a line when is_exact_pin is false.
    """
    failures: list[str] = []
    for name, spec in sorted(pins.items()):
        if not is_exact_pin(spec, kind):
            failures.append(
                f"{label}: {name} specifier {spec!r} is not an exact pin"
            )
    return failures


def pep503(name: str) -> str:
    """
    What: Normalize a Python distribution name for comparison.
    Why: Flask and flask are the same package on the allowlist.
    Who: declared_python and check_side when they pair names.
    Where: Backend requirement lines vs approved-packages.json keys.
    How: Lowercase, then replace runs of -, _, or . with a single hyphen.
    """
    return re.sub(r"[-_.]+", "-", (name or "").strip().lower())


def declared_python(path: Path, seen: set[Path] | None = None) -> dict[str, str]:
    """
    What: Read declared requirement names and specifiers from a requirements file.
    Why: The gate must see both product and dev lists without adding packages.
    Who: load_declared for backend/requirements.txt and requirements-dev.txt.
    Where: Lines that are not comments. -r includes are followed once.
    How: Skip blanks and #. Recurse on -r. Keep the last specifier per PEP 503 name.
    """
    found: dict[str, str] = {}
    walked = seen if seen is not None else set()
    resolved = path.resolve()
    if resolved in walked or not path.is_file():
        return found
    walked.add(resolved)
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r "):
            nested = (path.parent / line[3:].strip()).resolve()
            found.update(declared_python(nested, walked))
            continue
        match = REQ_NAME.match(line)
        if not match:
            continue
        name = pep503(match.group(1))
        spec = (match.group(2) or "").strip()
        found[name] = spec
    return found


def declared_node(path: Path) -> dict[str, str]:
    """
    What: Read dependency names and specifiers from a package.json.
    Why: Frontend product and toolchain names must stay on the same allowlist.
    Who: load_declared for frontend/package.json.
    Where: dependencies and devDependencies only. Not optionalDependencies.
    How: Load JSON; copy each name to its version string.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    for bucket in ("dependencies", "devDependencies"):
        block = data.get(bucket) or {}
        if isinstance(block, dict):
            for name, spec in block.items():
                found[str(name)] = str(spec)
    return found


def load_allowlist(path: Path) -> dict[str, dict[str, str]]:
    """
    What: Load the pinned backend and frontend allowlist from disk.
    Why: The gate and the docs page must share one list.
    Who: main and the tests that call check_manifests.
    Where: approved-packages.json at the repo root.
    How: JSON object with backend and frontend maps of name to specifier.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    backend = {pep503(name): str(spec) for name, spec in (data.get("backend") or {}).items()}
    frontend = {str(name): str(spec) for name, spec in (data.get("frontend") or {}).items()}
    return {"backend": backend, "frontend": frontend}


def check_side(label: str, declared: dict[str, str], allowed: dict[str, str]) -> list[str]:
    """
    What: Compare one manifest to its allowlist and collect failure lines.
    Why: An extra name must fail. A missing current-tree name must also fail.
    Who: check_manifests for backend and frontend.
    Where: Failure text printed by main.
    How: Extra keys, missing keys, then specifier mismatches.
    """
    failures: list[str] = []
    extra = sorted(set(declared) - set(allowed))
    missing = sorted(set(allowed) - set(declared))
    for name in extra:
        failures.append(f"{label}: {name} is not on the approved list")
    for name in missing:
        failures.append(f"{label}: allowlist package {name} is missing from the tree")
    for name in sorted(set(declared) & set(allowed)):
        if declared[name] != allowed[name]:
            failures.append(
                f"{label}: {name} specifier {declared[name]!r} does not match pin {allowed[name]!r}"
            )
    return failures


def check_manifests(root: Path | None = None) -> list[str]:
    """
    What: Run the declared-package allowlist against this repo's manifests.
    Why: make packages / make ci must fail a new first-party dependency.
    Who: main and backend/tests/test_packages.py.
    Where: requirements files and frontend/package.json vs approved-packages.json.
    How: Load both sides, check_side for backend and frontend, then check_exact on declared and allowlist maps.
    """
    base = root or ROOT
    allow = load_allowlist(base / "approved-packages.json")
    backend = declared_python(base / "backend" / "requirements-dev.txt")
    frontend = declared_node(base / "frontend" / "package.json")
    failures: list[str] = []
    failures.extend(check_side("backend", backend, allow["backend"]))
    failures.extend(check_side("frontend", frontend, allow["frontend"]))
    failures.extend(check_exact("backend", backend, "python"))
    failures.extend(check_exact("backend-allowlist", allow["backend"], "python"))
    failures.extend(check_exact("frontend", frontend, "node"))
    failures.extend(check_exact("frontend-allowlist", allow["frontend"], "node"))
    return failures


def main(argv: list[str] | None = None) -> int:
    """
    What: CLI entry for the approved-package gate.
    Why: make packages needs a process exit code, not a Python list.
    Who: scripts/check.sh packages and make packages.
    Where: Repo root via ROOT.
    How: Print each failure line and return 1 when the list is not empty.
    """
    del argv
    failures = check_manifests()
    if failures:
        for line in failures:
            print(line, file=sys.stderr)
        return 1
    print("approved-package check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
