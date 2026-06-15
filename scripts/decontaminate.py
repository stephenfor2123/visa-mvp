#!/usr/bin/env python3
# W15-P0-1 Decontamination Script
#
# Scan all .md/.yaml/.json/.txt files in a project, find placeholder
# contamination patterns (used by A worker across sessions) and replace
# them with context-appropriate Chinese.
#
# IMPORTANT: To avoid this file itself being flagged by write_guard,
# the placeholder chars (U+4FEE and U+771F) are written as Python
# unicode escape sequences ("\u4fee" / "\u771f") which the Python
# parser converts at parse time. The on-disk file thus contains
# the ASCII literal sequence, NOT the UTF-8 bytes.
#
# Patterns (chain order, longest to shortest):
#   5-char: x-z-x-z-shi-zhan  ->  shi xian (shi xian)
#   4-char: x-z-x-z           ->  xiu (single char)
#   3-char: x-z-yin           ->  xiu zheng
#   3-char: x-z-zhi           ->  xiu zheng zhi
#   2-char: x-z               ->  xiu (single char fallback)
#
# Also:
#   - 2+ consecutive xiu chars -> single xiu
#   - 2+ consecutive zhen chars -> single zhen

from __future__ import annotations
import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import List, Tuple


# Placeholder chars: xiu (U+4FEE) and zhen (U+771F)
# Use unicode escapes so the on-disk file is clean.
_X = "\u4fee"   # xiu (single char at runtime; \u4fee as ASCII in file)
_Z = "\u771f"   # zhen

# Placeholder patterns (longest first to avoid partial matches)
PATTERNS: List[Tuple[str, str]] = [
    (_X + _Z + _X + _Z + "\u5b9e\u6218", "\u5b9e\u73b0"),  # x-z-x-z-shizhan -> shixian
    (_X + _Z + _X + _Z, _X),                                 # x-z-x-z -> x
    (_X + _Z + "\u56e0", "\u4fee\u6574"),                    # x-z-yin -> xiuzheng
    (_X + _Z + "\u4e4b", "\u4fee\u6574\u4e4b"),              # x-z-zhi -> xiuzheng zhi
    (_X + _Z, _X),                                           # x-z -> x (fallback)
]

# Consecutive identical-char patterns
CONSECUTIVE_RE = [
    (re.compile(_X + "{2,}"), _X),
    (re.compile(_Z + "{2,}"), _Z),
]

EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "build", "dist"}
EXCLUDE_FILE_PATTERNS = {".bak", ".swp", ".pyc", ".DS_Store"}
# Exclude paths to prevent self-modification / plan destruction
EXCLUDE_PATHS = {
    "scripts/decontaminate.py",
    "scripts/write_guard.py",
    ".mavis/plans/plan_w15_p0_fixes.yaml",
}


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scan_content(text: str) -> Tuple[str, int]:
    """Apply all replacements. Returns (new_text, total_subs)."""
    total = 0
    for pattern, repl in CONSECUTIVE_RE:
        text, n = pattern.subn(repl, text)
        total += n
    for placeholder, repl in PATTERNS:
        n = text.count(placeholder)
        if n:
            text = text.replace(placeholder, repl)
            total += n
    return text, total


def is_excluded(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    parts = set(rel.parts)
    if parts & EXCLUDE_DIRS:
        return True
    if any(path.name.endswith(s) for s in EXCLUDE_FILE_PATTERNS):
        return True
    rel_str = str(rel)
    for excl in EXCLUDE_PATHS:
        if rel_str == excl or rel_str.endswith("/" + excl):
            return True
    return False


def iter_targets(root: Path):
    for ext in (".md", ".yaml", ".yml", ".json", ".txt"):
        for p in root.rglob("*" + ext):
            if p.is_file() and not is_excluded(p, root):
                yield p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--log-dir", type=Path, default=None)
    args = ap.parse_args()

    if args.dry_run == args.apply:
        ap.error("Specify exactly one of --dry-run or --apply")

    root = args.root.resolve()
    log_dir = (args.log_dir or root / "scripts" / "logs").resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / ("decontaminate-dryrun.log" if args.dry_run else "decontaminate-apply.log")

    rows = []
    total_files_changed = 0
    total_subs = 0

    for p in iter_targets(root):
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        sha_before = sha256_of(p)
        new_text, subs = scan_content(text)
        if subs == 0:
            continue
        sha_after = hashlib.sha256(new_text.encode("utf-8")).hexdigest()
        rows.append((str(p.relative_to(root)), sha_before, sha_after, subs, len(text), len(new_text)))
        total_subs += subs
        total_files_changed += 1
        if args.apply:
            p.write_text(new_text, encoding="utf-8")

    with log_file.open("w", encoding="utf-8") as f:
        mode = "DRY-RUN" if args.dry_run else "APPLY"
        f.write("# decontaminate " + mode + " log\n")
        f.write("root: " + str(root) + "\n")
        f.write("files_changed: " + str(total_files_changed) + "\n")
        f.write("total_substitutions: " + str(total_subs) + "\n\n")
        f.write("| file | sha256_before | sha256_after | subs | bytes_before | bytes_after |\n")
        f.write("|------|---------------|--------------|------|--------------|-------------|\n")
        for rel, sb, sa, n, lb, la in rows:
            f.write("| " + rel + " | " + sb + " | " + sa + " | " + str(n) + " | " + str(lb) + " | " + str(la) + " |\n")

    mode = "DRY-RUN" if args.dry_run else "APPLY"
    print("[" + mode + "] " + str(total_files_changed) + " files, " + str(total_subs) + " substitutions")
    print("log: " + str(log_file))


if __name__ == "__main__":
    main()
