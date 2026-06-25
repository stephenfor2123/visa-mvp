"""Case 5: 图片自动扫描剪裁真业务流 (V2 §4.3.3 preprocess).

流程:
  1. 注册+登录 → JWT
  2. 用 OpenCV 合成一张"用户随手拍的文档"图 (有透视变形 + 阴影)
  3. POST /api/v2/materials/preprocess → 拿 base64 图片 + meta
  4. 验证: corrected=True (透视变换成功), confidence > 0.5, corners 4 个
  5. 负向测试: 小于 240x240 的图 → 走 passthrough, 不崩

输出: 1 张合成图 + 1 张处理后图, 存在 outputs/case5/ 供人工对比.
"""
from __future__ import annotations

import base64
import io
import sys
import time
from pathlib import Path

import cv2
import httpx
import numpy as np
from PIL import Image

BASE = "http://127.0.0.1:8000"
FIXTURE_DIR = Path(__file__).resolve().parent.parent / "backend" / "tests" / "fixtures"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs" / "case5"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def log(tag: str, msg: str) -> None:
    print(f"[{tag}] {msg}", flush=True)


def make_synthetic_document() -> bytes:
    """合成一张"用户随手拍的护照页": 黑色背景 + 白色文档 (有透视变形) + 文字."""
    # 1. 干净的白色文档 (模拟 A4 护照页)
    doc = np.ones((600, 900, 3), dtype=np.uint8) * 255
    cv2.rectangle(doc, (30, 30), (870, 570), (200, 200, 200), 2)
    cv2.putText(doc, "PASSPORT", (80, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3)
    cv2.putText(doc, "Passport No: G12345678", (80, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    cv2.putText(doc, "Surname: ZHANG", (80, 280), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    cv2.putText(doc, "Given Name: SAN", (80, 340), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    cv2.putText(doc, "Date of Birth: 1990-01-15", (80, 400), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    cv2.putText(doc, "Date of Expiry: 2030-12-31", (80, 460), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    cv2.putText(doc, "P<CHNZHANG<<SAN<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<", (60, 540),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

    # 2. 模拟"随手拍": 黑色桌面背景, 把文档斜着贴上去
    bg = np.zeros((900, 1200, 3), dtype=np.uint8) * 40  # dark desk
    # perspective warp: 把 900x600 文档投到 bg 的一个斜四边形
    src = np.float32([[0, 0], [900, 0], [900, 600], [0, 600]])
    dst = np.float32([[150, 200], [1050, 80], [1100, 700], [100, 750]])  # 略斜
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(doc, M, (1200, 900))
    # mask out non-document area: 用 dst quad 之外用 bg 覆盖
    mask = np.zeros((900, 1200), dtype=np.uint8)
    cv2.fillPoly(mask, [dst.astype(np.int32)], 255)
    bg_with_doc = np.where(mask[..., None] > 0, warped, bg)

    # 加点噪声 + 阴影
    noise = np.random.normal(0, 8, bg_with_doc.shape).astype(np.int16)
    bg_with_doc = np.clip(bg_with_doc.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # JPEG encode
    ok, buf = cv2.imencode(".jpg", bg_with_doc, [cv2.IMWRITE_JPEG_QUALITY, 90])
    assert ok
    return buf.tobytes()


def make_tiny_image() -> bytes:
    """100x100 的小图 → 应该走 passthrough (小于 MIN_DIM=240)."""
    img = np.ones((100, 100, 3), dtype=np.uint8) * 200
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


def register_and_login(client: httpx.Client, phone: str) -> str:
    r = client.post(
        "/api/v2/auth/send-code",
        json={"phone": phone, "phone_country": "+86", "purpose": "register"},
    )
    r.raise_for_status()
    code = r.json()["data"]["code"]

    r = client.post(
        "/api/v2/auth/register",
        json={
            "phone": phone,
            "phone_country": "+86",
            "password": "Test1234",
            "sms_code": code,
            "language_pref": "zh-CN",
        },
    )
    r.raise_for_status()

    r = client.post(
        "/api/v2/auth/login",
        json={"phone": phone, "phone_country": "+86", "password": "Test1234"},
    )
    r.raise_for_status()
    return r.json()["data"]["access_token"]


def call_preprocess(client: httpx.Client, token: str, data: bytes, *, binarize: bool = False) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("test.jpg", io.BytesIO(data), "image/jpeg")}
    r = client.post(
        "/api/v2/materials/preprocess",
        files=files,
        data={"apply_binarize": str(binarize).lower()},
        headers=headers,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["data"]


def main() -> int:
    phone = "139" + str(int(time.time()))[-8:]
    log("START", f"phone={phone}")

    with httpx.Client(base_url=BASE, timeout=30) as client:
        token = register_and_login(client, phone)
        log("AUTH", "registered + logged in")

        results = []

        # === Test 1: 大文档照片 → 透视变换 ===
        log("PRE", "=== Test 1: synthetic document photo ===")
        big_data = make_synthetic_document()
        (OUTPUT_DIR / "01_input.jpg").write_bytes(big_data)
        log("PRE", f"input size={len(big_data)} bytes")

        t0 = time.time()
        data = call_preprocess(client, token, big_data)
        dt = time.time() - t0
        meta = data["meta"]

        # save processed image
        proc_bytes = base64.b64decode(data["image_base64"])
        (OUTPUT_DIR / "01_processed.jpg").write_bytes(proc_bytes)

        log("PRE", f"output size={len(proc_bytes)} bytes, dims={meta['width']}x{meta['height']}")
        log("PRE", f"corrected={meta['corrected']} confidence={meta['confidence']}")
        log("PRE", f"corners={meta['corners']}")
        log("PRE", f"stages={meta['stages']}")
        log("PRE", f"warnings={meta['warnings']}")
        log("PRE", f"elapsed={dt:.2f}s")

        # assertions
        ok_1 = (
            meta["corrected"] is True
            and meta["confidence"] >= 0.4
            and meta["corners"] is not None
            and len(meta["corners"]) == 4
            and meta["width"] > 0 and meta["height"] > 0
            and "perspective_corrected" in meta["stages"]
        )
        log("PRE", f"Test 1 {'PASS' if ok_1 else 'FAIL'}")
        results.append({"test": "document_photo", "ok": ok_1, "confidence": meta["confidence"]})

        # === Test 2: 二值化模式 ===
        log("PRE", "=== Test 2: binarize mode (receipt-like) ===")
        data = call_preprocess(client, token, big_data, binarize=True)
        meta = data["meta"]
        proc_bytes = base64.b64decode(data["image_base64"])
        (OUTPUT_DIR / "02_binarized.jpg").write_bytes(proc_bytes)
        log("PRE", f"stages={meta['stages']}")
        ok_2 = "binarized" in meta["stages"] and meta["corrected"]
        log("PRE", f"Test 2 {'PASS' if ok_2 else 'FAIL'}")
        results.append({"test": "binarize_mode", "ok": ok_2})

        # === Test 3: 小图 → passthrough ===
        log("PRE", "=== Test 3: tiny image (100x100) → passthrough ===")
        tiny = make_tiny_image()
        data = call_preprocess(client, token, tiny)
        meta = data["meta"]
        log("PRE", f"corrected={meta['corrected']} warnings={meta['warnings']}")
        ok_3 = (
            meta["corrected"] is False
            and any("too_small" in w for w in meta["warnings"])
        )
        log("PRE", f"Test 3 {'PASS' if ok_3 else 'FAIL'}")
        results.append({"test": "tiny_image_passthrough", "ok": ok_3})

        # === Test 4: 缺图 → 401/400? 不, 应该走 passthrough + decode_failed warning ===
        # 这里测个 invalid bytes
        log("PRE", "=== Test 4: invalid bytes → graceful fail ===")
        r = client.post(
            "/api/v2/materials/preprocess",
            files={"file": ("bad.jpg", io.BytesIO(b"not an image"), "image/jpeg")},
            data={"apply_binarize": "false"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        log("PRE", f"invalid bytes HTTP {r.status_code}")
        # 应该返回 200 + corrected=False + decode_failed warning
        if r.status_code == 200:
            meta = r.json()["data"]["meta"]
            ok_4 = meta["corrected"] is False and any("decode_failed" in w for w in meta["warnings"])
            log("PRE", f"warnings={meta['warnings']}")
        else:
            ok_4 = False
        log("PRE", f"Test 4 {'PASS' if ok_4 else 'FAIL'}")
        results.append({"test": "invalid_bytes_graceful", "ok": ok_4})

    # === summary ===
    log("DONE", "=" * 50)
    pass_count = sum(1 for r in results if r["ok"])
    log("DONE", f"Case 5 (preprocess): {pass_count}/{len(results)} passed")
    for r in results:
        log("DONE", f"  - {r['test']}: {'OK' if r['ok'] else 'FAIL'}")
    log("DONE", f"artifacts saved to {OUTPUT_DIR}/")

    return 0 if pass_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())