"""Display-only classification banner from CLASSIFICATION env.

This is a label. It is not an authorization to operate, and it is not a
claim that the demo can hold CUI or classified data.
"""

from __future__ import annotations

import os
import re

LEVELS = {
    "unclassified": {"color": "#007A33", "text": "UNCLASSIFIED"},
    "cui": {"color": "#502B85", "text": "CUI"},
    "confidential": {"color": "#0033A0", "text": "CONFIDENTIAL"},
    "secret": {"color": "#C8102E", "text": "SECRET"},
    "top_secret": {"color": "#FF8C00", "text": "TOP SECRET"},
    "itar": {"color": "#1B4D3E", "text": "CUI//SP-EXPT"},
}

ALIASES = {
    "u": "unclassified",
    "top secret": "top_secret",
    "topsecret": "top_secret",
    "ts": "top_secret",
    "c": "confidential",
    "s": "secret",
}

DISCLAIMER = "Label only. Not an authorization to operate."
_FALLBACK = LEVELS["unclassified"]
_WHITE = "#FFFFFF"
_BLACK = "#000000"
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def safe_hex_color(raw: str | None) -> str:
    """
    What: Normalize a custom banner color to a six-digit hex swatch.
    Why: A free-text CLASSIFICATION_CUSTOM_COLOR must not become a CSS injection.
    Who: banner() on the CUSTOM branch.
    Where: CLASSIFICATION_CUSTOM_COLOR from .env or the CI dropdown.
    How: Prepend # when it is missing; keep the value if it matches HEX_COLOR; otherwise #333333.
    """
    text = (raw or "").strip()
    if text and not text.startswith("#"):
        text = f"#{text}"
    if HEX_COLOR.fullmatch(text):
        return text
    return "#333333"


def _norm_key(raw: str) -> str:
    """
    What: Fold a CLASSIFICATION string into a LEVELS key or alias.
    Why: Dropdown values, slugs, and short letters must resolve the same way.
    Who: banner() before it looks up LEVELS or the custom branch.
    Where: CLASSIFICATION env from .env or the GitLab CI/CD dropdown.
    How: Lowercase, treat hyphen/underscore as space, then apply ALIASES.
    """
    key = " ".join(
        (raw or "").strip().lower().replace("-", " ").replace("_", " ").split()
    )
    if key in ALIASES:
        return ALIASES[key]
    return key.replace(" ", "_")


def _hex_rgb(color: str) -> tuple[float, float, float]:
    """
    What: Parse a hex color into 0–1 sRGB channels.
    Why: Luminance math needs numeric channels, not a CSS string.
    Who: _rel_lum after the banner color is chosen.
    Where: LEVELS colors and CLASSIFICATION_CUSTOM_COLOR.
    How: Accept #RGB or #RRGGBB; fall back to unclassified green when invalid.
    """
    raw = (color or "").strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6:
        raw = "007A33"
    try:
        red = int(raw[0:2], 16) / 255.0
        green = int(raw[2:4], 16) / 255.0
        blue = int(raw[4:6], 16) / 255.0
    except ValueError:
        return (0.0, 122.0 / 255.0, 51.0 / 255.0)
    return (red, green, blue)


def _format_hex(color: str) -> str:
    """
    What: Normalize a paint color to uppercase #RRGGBB.
    Why: The SPA and tests compare one spelling of each swatch.
    Who: banner() when it returns color.
    Where: LEVELS swatches and CLASSIFICATION_CUSTOM_COLOR.
    How: Expand #RGB, reject junk, default to unclassified green.
    """
    raw = (color or "").strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6:
        return _FALLBACK["color"]
    try:
        int(raw, 16)
    except ValueError:
        return _FALLBACK["color"]
    return f"#{raw.upper()}"


def _channel_lin(srgb: float) -> float:
    """
    What: Convert one gamma-encoded sRGB channel to linear light.
    Why: WCAG relative luminance is defined on linear values, not bytes.
    Who: _rel_lum for the red, green, and blue channels.
    Where: Banner ink contrast against the classification paint.
    How: IEC 61966-2-1 — divide by 12.92 under 0.04045, else the 2.4 curve.
    """
    if srgb <= 0.04045:
        return srgb / 12.92
    return ((srgb + 0.055) / 1.055) ** 2.4


def _rel_lum(color: str) -> float:
    """
    What: WCAG relative luminance of a hex color.
    Why: Contrast ratio needs the lighter and darker luminance pair.
    Who: _contrast_ratio for paint versus black or white ink.
    Where: Classification banner colors only.
    How: 0.2126 R + 0.7152 G + 0.0722 B after _channel_lin on each channel.
    """
    red, green, blue = _hex_rgb(color)
    return (
        0.2126 * _channel_lin(red)
        + 0.7152 * _channel_lin(green)
        + 0.0722 * _channel_lin(blue)
    )


def _contrast_ratio(first: str, second: str) -> float:
    """
    What: WCAG contrast ratio between two hex colors.
    Why: Ink must be the higher-contrast choice, not a hardcoded map.
    Who: _ink_for comparing black and white against the paint.
    Where: Banner foreground decision.
    How: (lighter + 0.05) / (darker + 0.05) using _rel_lum of each side.
    """
    left = _rel_lum(first)
    right = _rel_lum(second)
    lighter = max(left, right)
    darker = min(left, right)
    return (lighter + 0.05) / (darker + 0.05)


def _ink_for(color: str) -> str:
    """
    What: Pick black or white ink for a classification paint color.
    Why: TOP SECRET orange fails WCAG with white; black must win that swatch.
    Who: banner() when it fills the ink field.
    Where: Returned JSON classification.ink for the SPA banners.
    How: Compare WCAG ratios vs #000000 and #FFFFFF; keep the higher score.
    """
    black_ratio = _contrast_ratio(color, _BLACK)
    white_ratio = _contrast_ratio(color, _WHITE)
    if black_ratio >= white_ratio:
        return _BLACK
    return _WHITE


def banner() -> dict:
    """
    What: Build the display-only classification payload from the process env.
    Why: /api/copy and the SPA banners must share one label, color, and ink.
    Who: api_copy in app.py; tests in test_classification.py.
    Where: CLASSIFICATION plus CLASSIFICATION_TEXT and CLASSIFICATION_CUSTOM_*.
    How: Resolve the dropdown key, apply text/color overrides, then WCAG ink.
    """
    key = _norm_key(os.environ.get("CLASSIFICATION") or "")
    if key == "custom":
        level = "custom"
        text = (os.environ.get("CLASSIFICATION_CUSTOM_TEXT") or "").strip() or "CUSTOM"
        color = safe_hex_color(os.environ.get("CLASSIFICATION_CUSTOM_COLOR") or "")
    elif key in LEVELS:
        spec = LEVELS[key]
        level = key
        text = spec["text"]
        color = spec["color"]
    else:
        spec = _FALLBACK
        level = "unclassified"
        text = spec["text"]
        color = spec["color"]
    override = (os.environ.get("CLASSIFICATION_TEXT") or "").strip()
    if override:
        text = override
    return {
        "level": level,
        "text": text,
        "color": color,
        "ink": _ink_for(color),
        "disclaimer": DISCLAIMER,
    }
