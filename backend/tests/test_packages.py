"""Approved-package allowlist gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_packages import check_manifests, check_side, pep503


def test_current_tree_passes():
    assert check_manifests() == []


def test_pep503_folds_flask():
    assert pep503("Flask") == "flask"
    assert pep503("pytest_cov") == "pytest-cov"


def test_extra_backend_name_fails():
    fails = check_side("backend", {"flask": ">=3.0.0", "requests": ">=2"}, {"flask": ">=3.0.0"})
    assert any("requests is not on the approved list" in line for line in fails)


def test_missing_allowlist_name_fails():
    fails = check_side("frontend", {"react": "^18.3.1"}, {"react": "^18.3.1", "vite": "^5.4.8"})
    assert any("allowlist package vite is missing" in line for line in fails)


def test_specifier_mismatch_fails():
    fails = check_side("backend", {"flask": ">=99"}, {"flask": ">=3.0.0"})
    assert any("does not match pin" in line for line in fails)


def test_injected_requirement_fails(tmp_path):
    allow = {
        "note": "test",
        "backend": {"flask": ">=3.0.0"},
        "frontend": {"react": "^18.3.1"},
    }
    (tmp_path / "approved-packages.json").write_text(json.dumps(allow), encoding="utf-8")
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "requirements.txt").write_text("Flask>=3.0.0\nrequests>=2.0.0\n", encoding="utf-8")
    (backend / "requirements-dev.txt").write_text("-r requirements.txt\n", encoding="utf-8")
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text(
        json.dumps({"dependencies": {"react": "^18.3.1"}, "devDependencies": {}}),
        encoding="utf-8",
    )
    fails = check_manifests(tmp_path)
    assert any("requests is not on the approved list" in line for line in fails)
