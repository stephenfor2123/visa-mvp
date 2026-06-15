#!/usr/bin/env python3
# W15-P0-1 Write Guard
#
# Prevents the cross-session contamination pattern (x-z adjacent chars
# in Chinese text) from being written to disk via write_safe().
#
# IMPORTANT: To avoid this file itself being flagged, the placeholder
# chars (U+4FEE and U+771F) are written as Python unicode escapes
# ("\u4fee" / "\u771f") which Python converts at parse time.
# The on-disk file thus contains the ASCII literal sequence, NOT the
# UTF-8 bytes for those chars.
#
# Patterns detected (all raise ContaminationError / ValueError):
#   - 2+ consecutive xiu chars (xiuxiu)
#   - 2+ consecutive zhen chars (zhenzhen)
#   - x-z base
#   - x-z-shi-zhan (5-char variant)
#   - x-z-x-z (4-char dup variant)
#   - x-z-yin, x-z-zhi (3-char variants)
#   - (x-z){2,} repeating pattern
#   - x-z + 1 chinese char
#
# Usage:
#   from scripts.write_guard import write_safe, ContaminationError
#   write_safe("any text")          # raises if contaminated
#   write_safe("...", allow=True)   # skip check (system content only)

from __future__ import annotations
import re
import sys
from typing import List, Tuple


# Placeholder chars at runtime
_X = "\u4fee"   # xiu
_Z = "\u771f"   # zhen

# Suggestion alternatives (legit Chinese, no x-z adjacent)
SUGGESTIONS = [
    "\u4fee\u6574",   # xiuzheng
    "\u5b9e\u6d4b",   # shice
    "\u4fee\u540e",   # xiuhou
    "\u4fee\u4e00\u6b21",  # xiu yici
    "\u843d\u5b9e",   # luoshi
    "\u786c\u4e0a",   # ying shang
    "\u5b9e\u64cd",   # shicao
]

# All contamination patterns
XZ_SHORT = _X + _Z
XZ_VARIANTS = [
    _X + _Z + _X + _Z + "\u5b9e\u6218",   # x-z-x-z-shizhan
    _X + _Z + _X + _Z,                     # x-z-x-z
    _X + _Z + "\u56e0",                    # x-z-yin
    _X + _Z + "\u4e4b",                    # x-z-zhi
    _X + _Z,                               # x-z
]

PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(_X + "{2,}"), "consecutive-xiu"),
    (re.compile(_Z + "{2,}"), "consecutive-zhen"),
    # Longest x-z variants first
    (re.compile(re.escape(_X + _Z + _X + _Z + "\u5b9e\u6218")), "xz-shizhan-variant"),
    (re.compile(re.escape(_X + _Z + _X + _Z)), "xz-dup-variant"),
    (re.compile(re.escape(_X + _Z + "\u56e0")), "xz-yin-variant"),
    (re.compile(re.escape(_X + _Z + "\u4e4b")), "xz-zhi-variant"),
    # Repeating x-z pattern
    (re.compile("(?:" + re.escape(_X + _Z) + "){2,}"), "xz-repeat-2x+"),
    # x-z + 1 chinese char
    (re.compile(_X + _Z + r"[\u4e00-\u9fff]", re.UNICODE), "xz-1-chinese"),
    # Base x-z
    (re.compile(re.escape(_X + _Z)), "xz-base"),
]


def _suggest() -> str:
    return "Suggested replacements: " + " / ".join(SUGGESTIONS)


class ContaminationError(ValueError):
    """Raised when write_safe() detects cross-session contamination."""
    pass


def write_safe(content: str, *, allow: bool = False) -> str:
    """Validate content for x-z-adjacent contamination.

    Args:
        content: text to validate
        allow: if True, skip validation (use only for system content
               like the cleanup script's own error messages)

    Returns:
        content unchanged if clean

    Raises:
        ContaminationError: when any contamination pattern matches.
            Message includes the matched pattern label and a
            list of alternative word suggestions.
    """
    if allow:
        return content

    hits: List[str] = []
    for pat, label in PATTERNS:
        m = pat.search(content)
        if m:
            hits.append(label + "(" + m.group(0) + ")")
    if hits:
        msg = (
            "cross-session contamination detected: "
            + ", ".join(hits)
            + " | " + _suggest()
        )
        raise ContaminationError(msg)
    return content


def assert_clean(content: str) -> bool:
    """Return True if content has no contamination, False otherwise.
    Useful for one-off checks without try/except.
    """
    try:
        write_safe(content)
        return True
    except ContaminationError:
        return False


# CLI interface
def _main():
    import argparse
    ap = argparse.ArgumentParser(description="Check stdin or file for x-z contamination.")
    ap.add_argument("path", nargs="?", help="file path (omit to read stdin)")
    ap.add_argument("--quiet", action="store_true", help="exit 0/1 without message on success")
    args = ap.parse_args()

    if args.path:
        with open(args.path, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    try:
        write_safe(text)
    except ContaminationError as e:
        print("CONTAMINATED: " + str(e), file=sys.stderr)
        sys.exit(2)

    if not args.quiet:
        print("CLEAN: " + str(len(text)) + " chars, no x-z-adjacent contamination")
    sys.exit(0)


if __name__ == "__main__":
    _main()
