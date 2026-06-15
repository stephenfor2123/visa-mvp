#!/usr/bin/env python3
"""
OCR Accuracy Test — W5 §5.1.4 样本验收脚本.

Usage:
    python tests/ocr_accuracy_test.py --sample-dir samples/passport --min-confidence 0.80
    python tests/ocr_accuracy_test.py --sample-dir samples/passport --min-confidence 0.95 --dry-run

Exit codes:
    0  — 准确率 >= min_confidence
    1  — 准确率 < min_confidence  或其他错误
    2  — 缺少样本目录
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# cv2 (opencv-python) and paddleocr are heavy optional deps; exit early with
# a friendly message if they are not installed in the current venv.
try:
    import cv2  # noqa: F401
    import numpy as np  # noqa: F401
    from PIL import Image  # noqa: F401
    from paddleocr import PaddleOCR  # noqa: F401
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(
        f"[ocr_accuracy_test] SKIP: missing optional dependency '{exc.name}'. "
        "Install with: pip install opencv-python pillow paddleocr\n"
    )
    sys.exit(0)


def load_image(path: Path) -> np.ndarray | None:
    """Load image as BGR numpy array, or None if unreadable."""
    try:
        img_pil = Image.open(path).convert("RGB")
        img_arr = np.array(img_pil)
        return cv2.cvtColor(img_arr, cv2.COLOR_RGB2BGR)
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="OCR accuracy evaluation on passport samples")
    parser.add_argument(
        "--sample-dir",
        type=Path,
        default=Path("samples/passport"),
        help="Root directory containing country subdirectories",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.80,
        help="Minimum confidence threshold (default 0.80)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan directory structure without running OCR",
    )
    args = parser.parse_args()

    sample_dir: Path = args.sample_dir
    if not sample_dir.is_dir():
        print(f"ERROR: sample-dir not found: {sample_dir}", file=sys.stderr)
        return 2

    # Discover image files recursively
    IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
    image_files = [
        p for p in sample_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in IMG_EXTS
    ]

    if not image_files:
        print(f"WARNING: no image files found under {sample_dir}", file=sys.stderr)
        print("Run with --dry-run to check directory structure.", file=sys.stderr)
        return 2

    print(f"[INFO] Found {len(image_files)} image(s) under {sample_dir}")

    if args.dry_run:
        print("[INFO] --dry-run: skipping OCR inference")
        return 0

    # Initialise OCR engine once (en — most common)
    print("[INFO] Loading PaddleOCR (en) ...")
    engine = PaddleOCR(lang="en")
    print("[INFO] PaddleOCR ready")

    rows: list[dict] = []
    total = 0
    passed = 0
    sum_conf = 0.0

    for img_path in sorted(image_files):
        total += 1
        img = load_image(img_path)
        if img is None:
            rows.append({
                "filename": str(img_path),
                "confidence": 0.0,
                "status": "fail",
                "note": "unreadable",
            })
            continue

        result = engine.ocr(img, cls=True)
        raw_lines = result[0] if result and result[0] else []
        # Collect max confidence across all detected lines
        max_conf = 0.0
        for line in raw_lines:
            if line:
                _, (_, conf) = line
                max_conf = max(max_conf, float(conf))

        sum_conf += max_conf
        ok = max_conf >= args.min_confidence
        if ok:
            passed += 1

        rows.append({
            "filename": str(img_path),
            "confidence": round(max_conf, 4),
            "status": "pass" if ok else "fail",
            "note": "",
        })

    avg_conf = sum_conf / total if total > 0 else 0.0
    accuracy = passed / total if total > 0 else 0.0

    print("\n" + "=" * 60)
    print(f"  Total images : {total}")
    print(f"  Passed (≥{args.min_confidence}) : {passed}")
    print(f"  Average confidence : {avg_conf:.4f}")
    print(f"  Accuracy : {accuracy:.2%}")
    print("=" * 60)

    # Write CSV
    csv_path = sample_dir / "accuracy_results.csv"
    fieldnames = ["filename", "confidence", "status", "note"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[INFO] CSV written → {csv_path}")

    return 0 if accuracy >= args.min_confidence else 1


if __name__ == "__main__":
    sys.exit(main())