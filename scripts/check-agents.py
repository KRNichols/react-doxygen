#!/usr/bin/env python3
"""Docs-writer loop chrome gates. Product CI stays in ci.yml."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

def fail(msg):
    print("agents overlay FAIL:", msg, file=sys.stderr)
    sys.exit(1)

FORBIDDEN = [
    "frontend/src/Hornet.jsx",
    "frontend/src/Hornet.css",
    "frontend/src/components/Hornet.jsx",
    "frontend/src/flyout.css",
    "frontend/src/components/DocsHero.jsx",
    "frontend/src/pages/DocsHero.jsx",
]

def src_files():
    src = ROOT / "frontend" / "src"
    for path in src.rglob("*"):
        if path.suffix in {".js", ".jsx", ".css"} and ".test." not in path.name:
            yield path

def src_has(needle):
    return any(needle in path.read_text(encoding="utf-8") for path in src_files())

def main():
    for rel in FORBIDDEN:
        if (ROOT / rel).exists():
            fail("forbidden file " + rel)
    if src_has("data-flyout"):
        fail("data-flyout still present")
    if src_has("DocsHero"):
        fail("DocsHero still referenced")
    app = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
    if "querySelector" not in app or chr(34)+"main"+chr(34) not in app:
        fail("FocusOnRoute must target main")
    if "preventScroll" not in app:
        fail("FocusOnRoute must use preventScroll")
    parse = (ROOT / "frontend/src/docsParse.js").read_text(encoding="utf-8")
    if "function stripTitleAttributes" not in parse:
        fail("stripTitleAttributes missing")
    css = (ROOT / "frontend/src/pages/Docs.css").read_text(encoding="utf-8")
    if "docs-page-title:focus" not in css:
        fail("title focus rule missing")
    if "outline: none" not in css:
        fail("title focus must not be a filled box")
    print("agents overlay chrome gates passed")

if __name__ == "__main__":
    main()
