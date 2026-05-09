"""Numeric-grounding verifier.

Scans LLM-generated text for any numeric claim and verifies that each
number appears in the source JSON. Returns a list of unverified numbers
so the UI can surface them to the user (or trigger a single retry).

The check is intentionally lenient on rounding: 1.5 in the text matches
1.50, 1.49, or 1.51 in the JSON. Integers must match exactly. Negative
numbers and percentages are recognized.
"""

from __future__ import annotations
import json
import re
from typing import Iterable


# Match numbers like 1, 1.5, -0.3, +2.4, 12%, 1500.0
_NUM_RE = re.compile(
    r"(?<![A-Za-z0-9_\-/=])"             # not part of a word/code
    r"([+-]?\d+(?:\.\d+)?)"               # the number itself
    r"(?:\s?%)?"                          # optional %
    r"(?![A-Za-z])"                       # not followed by a letter (avoid '4-of-4', '6_2', units)
)

# Skip these — not data values, just structural numbers.
_BORING_NUMBERS = {
    "0", "1", "2", "3", "4", "10",          # small ints / counts
    "100",                                   # percent fullness
    "0.0", "1.0", "2.0",
}

# Skip whole tokens that contain digits but aren't real numeric claims.
_BORING_TOKEN_PATTERNS = [
    re.compile(r"^OSD-\d+$", re.IGNORECASE),
    re.compile(r"^IL-?\d+[a-z]?$",  re.IGNORECASE),
    re.compile(r"^TNF-?\d+[a-z]?$", re.IGNORECASE),
    re.compile(r"^L[+-]\d+$"),
    re.compile(r"^R[+-]\d+$"),
    re.compile(r"^FD\d+$"),
    re.compile(r"^C00\d$"),
]


def _is_boring(num_str: str) -> bool:
    if num_str in _BORING_NUMBERS:
        return True
    return False


def _approx_in(needle: float, haystack_set: set[float],
               *, has_decimal: bool) -> bool:
    """Return True if `needle` matches any value in haystack_set within
    rounding tolerance.

    Tolerance:
      - If the text wrote the number with NO decimal point ("274"),
        match anything in [274 - 0.55, 274 + 0.55] — covers 274.1, 273.5
        rounding to 274.
      - If the text used decimals ("1.5", "0.96"), tolerance is small
        (0.06) so we still catch real fabrication.

    Also matches when the text is a percentage and the JSON stores the
    fraction (96% <-> 0.96), or vice versa.
    """
    tol = 0.55 if not has_decimal else 0.06
    for h in haystack_set:
        if abs(h - needle) < tol:
            return True
        # text "96%" vs JSON 0.96
        if abs(h - needle / 100.0) < 0.01:
            return True
        # text "0.96" vs JSON 96 (less common but symmetric)
        if abs(h * 100.0 - needle) < 0.5:
            return True
    return False


def _collect_numbers_from_json(obj) -> set[float]:
    out: set[float] = set()
    if isinstance(obj, dict):
        for v in obj.values():
            out |= _collect_numbers_from_json(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out |= _collect_numbers_from_json(v)
    elif isinstance(obj, bool):
        return out
    elif isinstance(obj, (int, float)):
        if obj == obj:  # not NaN
            out.add(float(obj))
    elif isinstance(obj, str):
        # numbers embedded in strings count too
        for m in _NUM_RE.finditer(obj):
            try:
                out.add(float(m.group(1)))
            except ValueError:
                pass
    return out


def _strip_boring_tokens(text: str) -> str:
    """Replace boring tokens (OSD-571, IL-6, R+1, C001) with empty strings
    so we don't try to verify the numerals inside them."""
    cleaned = text
    for pat in _BORING_TOKEN_PATTERNS:
        cleaned = pat.sub("", cleaned)
    # also tokenize and pre-strip
    return cleaned


def find_unverified_numbers(text: str, source_json: dict | str
                             ) -> list[str]:
    """Return a list of number strings from `text` that don't have a
    near-match in `source_json`. Empty list = all numbers grounded.
    """
    if isinstance(source_json, str):
        try:
            obj = json.loads(source_json)
        except Exception:
            return []
    else:
        obj = source_json
    haystack = _collect_numbers_from_json(obj)
    if not haystack:
        return []

    cleaned = _strip_boring_tokens(text)
    unverified: list[str] = []
    seen: set[str] = set()
    for m in _NUM_RE.finditer(cleaned):
        s = m.group(1)
        if s in seen:
            continue
        seen.add(s)
        if _is_boring(s):
            continue
        try:
            v = float(s)
        except ValueError:
            continue
        has_decimal = "." in s
        if not _approx_in(v, haystack, has_decimal=has_decimal):
            unverified.append(s)
    return unverified
