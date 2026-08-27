"""User-facing copy loader (cannot be named copy.py — that shadows stdlib copy).

copy.json defaults, then COPY_* env overlays.

SIGNUP_NOTIFY_EMAIL stays its own env (see signup_mail.notify_address).
Set COPY_FILE to load a different JSON file. Nested keys accept either
COPY_login_title or COPY_LOGIN_TITLE (section + key, case-insensitive).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_FILE = ROOT / "copy.json"

_cache: dict[str, Any] | None = None
_cached_path: Path | None = None
_cached_mtime: float | None = None


def _deepcopy(obj: Any) -> Any:
    """
    What: Recursively clone dicts/lists so callers cannot mutate the cache.
    Why: get_copy is cached; a shared reference would leak env overlays.
    Who: get_copy, _apply_env.
    Where: In-process copy cache for /api/copy and signup mail templates.
    How: Walk dict/list nodes and return new containers; leave scalars as-is.
    """
    if isinstance(obj, dict):
        return {k: _deepcopy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deepcopy(v) for v in obj]
    return obj


def copy_path() -> Path:
    """
    What: Resolve the JSON file that holds default user-facing strings.
    Why: Operators may point at a branded file via COPY_FILE.
    Who: get_copy (and tests that inspect the active path).
    Where: Backend process; COPY_FILE is absolute or relative to this package.
    How: Read COPY_FILE, else backend/copy.json next to this module.
    """
    override = (os.environ.get("COPY_FILE") or "").strip()
    if not override:
        return DEFAULT_FILE
    path = Path(override)
    return path if path.is_absolute() else (ROOT / path)


def _find_key(mapping: dict, name: str) -> str | None:
    """
    What: Look up a dict key, ignoring case.
    Why: COPY_LOGIN_TITLE must match login.title without extra env vars.
    Who: _set_path when walking COPY_* overlays.
    Where: Env overlay of the copy tree only.
    How: Exact hit first, then compare .lower() of each key.
    """
    if name in mapping:
        return name
    needle = name.lower()
    for key in mapping:
        if key.lower() == needle:
            return key
    return None


def _set_path(tree: dict, parts: list[str], value: str) -> bool:
    """
    What: Assign value at a nested path described by underscore-split parts.
    Why: One COPY_* var should overlay one string without a full JSON file.
    Who: _apply_env for each COPY_* variable.
    Where: Merged copy dict before it is cached / served.
    How: Match joined, camelCase, then longest section prefix, case-insensitive.
    """
    if not parts:
        return False

    joined = "".join(parts)
    key = _find_key(tree, joined)
    if key is not None and not isinstance(tree.get(key), dict):
        tree[key] = value
        return True

    if len(parts) >= 2:
        camel = parts[0] + "".join(
            (p[:1].upper() + p[1:]) if p else "" for p in parts[1:]
        )
        key = _find_key(tree, camel)
        if key is not None and not isinstance(tree.get(key), dict):
            tree[key] = value
            return True
        for i in range(len(parts) - 1, 0, -1):
            prefix = parts[:i]
            rest = parts[i:]
            joined_prefix = "".join(prefix)
            section = _find_key(tree, joined_prefix)
            if section is not None and isinstance(tree.get(section), dict):
                if _set_path(tree[section], rest, value):
                    return True
            camel_prefix = prefix[0] + "".join(
                (p[:1].upper() + p[1:]) if p else "" for p in prefix[1:]
            )
            section = _find_key(tree, camel_prefix)
            if section is not None and isinstance(tree.get(section), dict):
                if _set_path(tree[section], rest, value):
                    return True
            if i == 1:
                section = _find_key(tree, prefix[0])
                if section is not None and isinstance(tree.get(section), dict):
                    if _set_path(tree[section], rest, value):
                        return True

    if len(parts) == 1:
        key = _find_key(tree, parts[0])
        if key is not None:
            tree[key] = value
            return True
    return False


def _apply_env(tree: dict) -> dict:
    """
    What: Overlay COPY_* environment variables onto a copy tree.
    Why: Deployments can override one COPY_* string without editing copy.json.
    Who: get_copy after reading the file.
    Where: Process environment of the Flask app.
    How: Skip COPY_FILE; split the rest on _; walk with _set_path.
    """
    out = _deepcopy(tree)
    for name, raw in os.environ.items():
        if not name.startswith("COPY_") or name == "COPY_FILE":
            continue
        rest = name[5:]
        parts = [p for p in rest.split("_") if p]
        if parts:
            _set_path(out, parts, raw)
    return out


def _load_file(path: Path) -> dict:
    """
    What: Read and parse a copy JSON file.
    Why: Defaults live on disk so editors can change wording without code.
    Who: get_copy when the cache is cold or the file mtime changed.
    Where: COPY_FILE or backend/copy.json.
    How: UTF-8 json.loads; empty dict if missing or not an object.
    """
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def get_copy(*, force: bool = False) -> dict:
    """
    What: Return the merged user-facing copy dictionary.
    Why: Pages, BrandHeader/Footer, and signup mail share one source of truth.
    Who: Flask GET /api/copy and signup_mail._build_message.
    Where: In-memory cache, invalidated when the JSON file mtime changes.
    How: Load file (unless cached), apply COPY_* env, return a deep copy.
    """
    global _cache, _cached_path, _cached_mtime
    path = copy_path()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = None
    if (
        not force
        and _cache is not None
        and _cached_path == path
        and _cached_mtime == mtime
    ):
        return _deepcopy(_cache)
    merged = _apply_env(_load_file(path))
    _cache = merged
    _cached_path = path
    _cached_mtime = mtime
    return _deepcopy(merged)


def fill(template: str, **values: Any) -> str:
    """
    What: Replace {name}-style placeholders in a copy string.
    Why: Email and a few page lines interpolate applicant or session values.
    Who: signup_mail._build_message (and any caller of get_copy templates).
    Where: Notification subject/body and SPA strings that include {notifyEmail}.
    How: Sequential str.replace of each {key}; None becomes empty.
    """
    text = "" if template is None else str(template)
    for key, raw in values.items():
        token = "{" + key + "}"
        text = text.replace(token, "" if raw is None else str(raw))
    return text
