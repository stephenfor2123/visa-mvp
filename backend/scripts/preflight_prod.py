#!/usr/bin/env python3
"""Backend production preflight — run before docker rebuild / alembic upgrade.

Checks:
  1. OpenAPI schema builds (catches Pydantic Optional/forward-ref 500s)
  2. typing.Optional used under future annotations without import
  3. When ENV=prod (or --strict): MATERIAL_ENCRYPTION_KEY must be set
  4. Alembic migration chain has a single head

Usage:
  python scripts/preflight_prod.py
  python scripts/preflight_prod.py --strict   # also require encryption key
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
NEED = {
    "Optional",
    "List",
    "Dict",
    "Set",
    "Tuple",
    "Union",
    "Iterable",
    "Mapping",
    "Sequence",
    "Callable",
    "Literal",
}


def scan_typing_gaps() -> list[str]:
    gaps: list[str] = []
    for path in sorted(APP.rglob("*.py")):
        src = path.read_text(encoding="utf-8")
        if "from __future__ import annotations" not in src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError as exc:
            gaps.append(f"{path.relative_to(ROOT)}: syntax error: {exc}")
            continue
        imported: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module in (
                "typing",
                "typing_extensions",
            ):
                for alias in node.names:
                    imported.add("*" if alias.name == "*" else alias.name)
        if "*" in imported:
            continue
        used = {name for name in NEED if re.search(rf"\b{name}\s*\[", src)}
        missing = sorted(used - imported)
        if missing:
            gaps.append(
                f"{path.relative_to(ROOT)}: uses {missing} but does not import them"
            )
    return gaps


def check_openapi() -> str | None:
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("ENV", "test")
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    try:
        from app.main import create_app

        app = create_app()
        schema = app.openapi()
        n = len(schema.get("paths") or {})
        if n < 10:
            return f"openapi paths unexpectedly small: {n}"
    except Exception as exc:  # noqa: BLE001
        return f"openapi build failed: {exc}"
    return None


def check_alembic_heads() -> str | None:
    versions = ROOT / "alembic" / "versions"
    if not versions.exists():
        return "alembic/versions missing"
    revs: dict[str, str] = {}
    for p in versions.glob("*.py"):
        text = p.read_text(encoding="utf-8")
        m = re.search(r"^revision\s*[:=]\s*[\"']([^\"']+)[\"']", text, re.M)
        d = re.search(r"^down_revision\s*[:=]\s*(.+)$", text, re.M)
        if not m:
            continue
        revs[m.group(1)] = (d.group(1).strip() if d else "None")
    parents: set[str] = set()
    for raw in revs.values():
        if raw in ("None", "None,"):
            continue
        for parent in re.findall(r"[\"']([^\"']+)[\"']", raw):
            parents.add(parent)
    heads = [r for r in revs if r not in parents]
    if len(heads) != 1:
        return f"expected 1 alembic head, found {heads}"
    return None


def check_encryption(strict: bool) -> str | None:
    env = (os.environ.get("ENV") or "").strip().lower()
    key = (os.environ.get("MATERIAL_ENCRYPTION_KEY") or "").strip()
    if strict or env == "prod":
        if not key:
            return "MATERIAL_ENCRYPTION_KEY required when ENV=prod / --strict"
        # 64 hex chars = 32 bytes, or urlsafe/std base64 (~43+ chars for 32 bytes)
        if len(key) == 64 and all(c in "0123456789abcdefABCDEF" for c in key):
            return None
        if len(key) >= 40:
            return None
        return "MATERIAL_ENCRYPTION_KEY looks too short (want 64 hex or 32-byte base64)"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Require MATERIAL_ENCRYPTION_KEY even if ENV is not prod",
    )
    args = parser.parse_args()

    failures: list[str] = []

    print("preflight_prod: scanning typing gaps…")
    failures.extend(scan_typing_gaps())

    print("preflight_prod: building OpenAPI…")
    err = check_openapi()
    if err:
        failures.append(err)
    else:
        print("  OK openapi")

    print("preflight_prod: alembic heads…")
    err = check_alembic_heads()
    if err:
        failures.append(err)
    else:
        print("  OK single alembic head")

    err = check_encryption(args.strict)
    if err:
        failures.append(err)
    else:
        print("  OK encryption key policy")

    if failures:
        print("\npreflight_prod FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("\npreflight_prod passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
