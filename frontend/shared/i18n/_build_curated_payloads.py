"""Build the 4-locale resources_curated JSON payload from a canonical English source.

We do NOT call any LLM — the canonical English file is hand-curated against the
official sources, and the 3 translations are hand-written by a bilingual native
editor (or our internal team). This script just:

  1. Reads the canonical English source (one source of truth).
  2. Reads the matching 3 hand-written translation files.
  3. Merges each into the appropriate /frontend/shared/i18n/<lang>.json under
     the ``resources_curated`` top-level key.

Idempotent — re-running replaces the entire ``resources_curated`` object.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path("/Users/apple/Desktop/签证项目_副本")
PAYLOADS_DIR = ROOT / "frontend" / "shared" / "i18n" / "_curated_payloads"
I18N_DIR = ROOT / "frontend" / "shared" / "i18n"

LANGS = ["zh-CN", "en", "id", "vi"]

MARKER_START = "__RESOURCES_CURATED_PLACEHOLDER_START__"
MARKER_END = "__RESOURCES_CURATED_PLACEHOLDER_END__"


def _read_canonical(lang: str) -> dict:
    p = PAYLOADS_DIR / f"resources_curated.{lang}.json"
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _strip_existing(text: str) -> str:
    """Remove any previous ``resources_curated`` block.

    Strategy: regex-match the previous block and replace with a marker so we can
    splice the new block in. We look for the top-level key — by matching the
    leading whitespace + quote + key + quote + colon + open-brace on a line of
    its own (i.e. ``"resources_curated": {``) and walking brace-balanced until
    the matching close. The previous block is always at the bottom of the file
    (we always append), so a simpler approach: find the last ``},?\s*\n\\s*}\\s*$``
    before the trailing ``}`` of the file.
    """
    # Idempotency: regex out the most recent "resources_curated": { ... } block
    # by walking the brace stack, anchored to the key name.
    pattern = re.compile(
        r'^[ \t]*"resources_curated"\s*:\s*\{',
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        return text  # nothing to strip

    # Find the matching closing brace by scanning from m.end()-1
    start = m.start()
    body_start = m.end() - 1  # points at the "{"
    depth = 0
    i = body_start
    while i < len(text):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
        i += 1
    else:
        raise RuntimeError("brace counting failed")

    # Find the trailing comma (if any) after the block, before the next sibling
    after = text[end:]
    if after.startswith(","):
        end += 1

    return text[:start] + after.lstrip("\n").rstrip() + ("\n" if not after.startswith("}") else "")


def _insert_block(target_text: str, block_obj: dict) -> str:
    """Insert ``resources_curated`` block at the end of the file (just before
    the final ``}`` of the top-level object). Idempotent — strips first.
    """
    stripped = _strip_existing(target_text).rstrip()

    block_json = json.dumps(block_obj, ensure_ascii=False, indent=2)

    # ensure stripped ends with closing brace
    if not stripped.endswith("}"):
        stripped += "}"
    # strip the trailing brace for resplice
    if stripped.endswith("}"):
        head = stripped[:-1].rstrip()
        # add comma separator — either fresh (after stripping) or none if file had nothing
        if not head.endswith("}"):
            head = head.rstrip()
        else:
            head = head + ","
    else:
        head = stripped.rstrip()

    # Build the final: head + "\n  "resources_curated": { ... }\n}"
    # We assume the existing indent is 2 spaces.
    head = head.rstrip(",\n").rstrip()
    head = head + ",\n"
    return head + f'  "resources_curated": {block_json}\n}}\n'


def update_locale(lang: str) -> None:
    payload = _read_canonical(lang)
    if not payload:
        print(f"  [{lang}] no payload file, skipping")
        return

    i18n_path = I18N_DIR / f"{lang}.json"
    original = i18n_path.read_text(encoding="utf-8")
    updated = _insert_block(original, payload)
    i18n_path.write_text(updated, encoding="utf-8")
    print(f"  [{lang}] updated -> {i18n_path}")


if __name__ == "__main__":
    if not PAYLOADS_DIR.exists():
        raise SystemExit(f"payloads dir not found: {PAYLOADS_DIR}")
    for lc in LANGS:
        update_locale(lc)
    print("done.")
