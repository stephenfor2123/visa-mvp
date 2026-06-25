"""Batch OCR — backfill ocr_result for materials that haven't been OCR'd yet.

Picks all materials where ocr_status != 'done' AND file exists AND file size > 1KB,
calls /api/v2/ocr/recognize, and writes back ocr_result + ocr_status='done'.

Then re-runs the accuracy benchmark against MaterialClassifier.
"""
import asyncio
import json
import sys
import time
from io import BytesIO
from pathlib import Path

import httpx

sys.path.insert(0, "/Users/apple/Desktop/签证项目/backend")
import os
os.chdir("/Users/apple/Desktop/签证项目/backend")

from app.core.db import AsyncSessionLocal
from app.models.material import Material
from app.services import storage
from app.services.material_classifier import MaterialClassifier
from sqlalchemy import select

BASE = "http://127.0.0.1:8000"
MIN_FILE_SIZE = 1024  # skip 70-byte 1px test data


async def call_ocr(token: str, file_path: Path, mime: str) -> dict:
    """Call /api/v2/ocr/recognize via httpx (uses real user JWT)."""
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as client:
        with open(file_path, "rb") as f:
            r = await client.post(
                "/api/v2/ocr/recognize",
                files={"file": (file_path.name, f, mime)},
                data={"lang": "en"},
                headers={"Authorization": f"Bearer {token}"},
            )
        r.raise_for_status()
        return r.json().get("data", {})


async def get_token() -> str:
    phone = "139" + str(int(time.time()))[-8:]
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        r = await client.post(
            "/api/v2/auth/send-code",
            json={"phone": phone, "phone_country": "+86", "purpose": "register"},
        )
        r.raise_for_status()
        code = r.json()["data"]["code"]
        await client.post(
            "/api/v2/auth/register",
            json={
                "phone": phone,
                "phone_country": "+86",
                "password": "Test1234",
                "sms_code": code,
                "language_pref": "zh-CN",
            },
        )
        r = await client.post(
            "/api/v2/auth/login",
            json={"phone": phone, "phone_country": "+86", "password": "Test1234"},
        )
        r.raise_for_status()
        return r.json()["data"]["access_token"]


async def main() -> int:
    # W25 fix: optionally wipe all OCR results so we re-OCR with the new
    # passport-gate logic. Default behavior: keep what's already done, only
    # process missing ones. Pass --reset to force re-OCR.
    reset = "--reset" in sys.argv
    token = await get_token()
    print(f"[AUTH] got token")

    async with AsyncSessionLocal() as db:
        if reset:
            from sqlalchemy import update as sa_update
            print(f"[RESET] clearing all ocr_result + resetting status to pending...")
            await db.execute(sa_update(Material).values(ocr_status="pending", ocr_result=None))
            await db.commit()
            print(f"[RESET] done")

        rows = (await db.execute(
            select(Material).where(Material.ocr_status != "done").order_by(Material.id)
        )).scalars().all()
        print(f"[INIT] {len(rows)} materials need OCR")

        processed = 0
        skipped = 0
        failed = 0
        for r in rows:
            # resolve local file
            try:
                p = storage.path_for(r.storage_key)
            except Exception:
                print(f"  #{r.id:3d} SKIP (storage key invalid)")
                skipped += 1
                continue
            if not p.exists():
                print(f"  #{r.id:3d} SKIP (file missing: {p.name})")
                skipped += 1
                continue
            size = p.stat().st_size
            if size < MIN_FILE_SIZE:
                print(f"  #{r.id:3d} SKIP (size {size}B < {MIN_FILE_SIZE}B — synthetic 1px test data)")
                skipped += 1
                continue

            print(f"  #{r.id:3d} OCR {r.mime_type:18s} {size:6d}B {r.original_filename}", flush=True)
            try:
                t0 = time.time()
                data = await call_ocr(token, p, r.mime_type)
                dt = time.time() - t0
                items = data.get("items", [])
                fields = data.get("fields", {})
                # write back
                r.ocr_status = "done"
                r.ocr_result = json.dumps({
                    "fields": fields,
                    "text": "\n".join(it.get("text", "") for it in items),
                    "items_count": len(items),
                    "engine": "paddle+tesseract-fallback",
                }, ensure_ascii=False)
                await db.commit()
                print(f"        ✓ {len(items)} items, fields={list(fields.keys())[:5]} ({dt:.1f}s)")
                processed += 1
            except Exception as e:
                print(f"        ✗ failed: {e}")
                failed += 1

        print(f"\n[OCR DONE] processed={processed} skipped={skipped} failed={failed}")

        # ──── Re-run benchmark ────
        print("\n" + "=" * 60)
        print("BENCHMARK AFTER BATCH OCR")
        print("=" * 60)
        all_rows = (await db.execute(select(Material).order_by(Material.id))).scalars().all()
        cls = MaterialClassifier()

        for mode, label in [
            ("filename_only", "Mode A: filename + mime only (no OCR)"),
            ("with_ocr",     "Mode B: filename + mime + OCR fields"),
        ]:
            print(f"\n{label}")
            print("-" * 60)
            hit, miss, fallback = 0, 0, 0
            misses = []
            for r in all_rows:
                ocr = None
                if mode == "with_ocr" and r.ocr_status == "done" and r.ocr_result:
                    try:
                        ocr = json.loads(r.ocr_result)
                    except Exception:
                        ocr = None
                out = cls.classify(
                    original_filename=r.original_filename,
                    mime_type=r.mime_type or "",
                    ocr_result=ocr,
                )
                pred = out.predicted_type
                act = r.material_type
                ok = pred == act
                if ok:
                    hit += 1
                elif pred == "other":
                    fallback += 1
                else:
                    miss += 1
                    misses.append((r.id, r.original_filename, act, pred, out.confidence))
            tot = len(all_rows)
            print(f"  Total:        {tot}")
            print(f"  Hit:          {hit:3d} / {tot}  ({hit*100/tot:.1f}%)  ✓ correct")
            print(f"  Miss:         {miss:3d} / {tot}  ({miss*100/tot:.1f}%)  ✗ wrong type")
            print(f"  Fallback:     {fallback:3d} / {tot}  ({fallback*100/tot:.1f}%)  → other (no signal)")
            if misses:
                print(f"  Misses:")
                for id_, fn, act, pred, conf in misses:
                    print(f"    #{id_:3d} {fn[:38]:38s} actual={act:10s} predicted={pred:10s} conf={conf:.2f}")

        # also break down OCR coverage
        ocr_done_n = sum(1 for r in all_rows if r.ocr_status == "done")
        print(f"\n[OCR coverage] {ocr_done_n}/{len(all_rows)} ({ocr_done_n*100/len(all_rows):.1f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))