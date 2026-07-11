"""Add the W48 v0.2 DS-160 i18n keys to all four language files.

We mutate each file in place, inserting a new block of keys AFTER the existing
`ext_download_started` key inside the `orderdetail` object.  The keys we add
mirror the new `onGetDs160Code` / `onRotateDs160Code` / `onCopyDs160Code` /
`onOpenDs160Website` handlers added to OrderDetail.vue.

Usage:
    cd frontend && python3 ../scripts/_add_ds160_keys.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "frontend" / "shared" / "i18n"

# (key, zh-CN, en, vi, id)  -- strings must be valid JSON (double quotes only)
# 4 languages are kept in sync via the array length.
NEW_KEYS = [
    ("ds160_get_code_btn",                "🧩 生成 DS-160 code (辅助填表)",
                                          "🧩 Generate DS-160 code (autofill helper)",
                                          "🧩 Tạo mã DS-160 (trợ điền)",
                                          "🧩 Buat kode DS-160 (bantu isi otomatis)"),
    ("ds160_refresh_code_btn",             "🧩 刷新 DS-160 code",
                                          "🧩 Refresh DS-160 code",
                                          "🧩 Làm mới mã DS-160",
                                          "🧩 Segarkan kode DS-160"),
    ("ds160_get_code_ok",                  "✅ 已生成 code — 复制后到 Chrome 插件粘贴",
                                          "✅ Code generated — copy it and paste in the Chrome extension",
                                          "✅ Đã tạo mã — sao chép rồi dán vào tiện ích Chrome",
                                          "✅ Kode dibuat — salin dan tempel di ekstensi Chrome"),
    ("ds160_unchanged_hint",               "档案没变, 复用旧 code",
                                          "Archive unchanged — reusing the existing code",
                                          "Hồ sơ không đổi — dùng lại mã cũ",
                                          "Arsip tidak berubah — pakai kode lama"),
    ("ds160_unchanged_badge",              "复用",
                                          "Reused",
                                          "Dùng lại",
                                          "Pakai lagi"),
    ("ds160_code_panel_title",             "你的 DS-160 12 位 code",
                                          "Your 12-digit DS-160 code",
                                          "Mã DS-160 12 ký tự của bạn",
                                          "Kode DS-160 12 digit Anda"),
    ("ds160_copy_btn",                     "复制 code",
                                          "Copy code",
                                          "Sao chép mã",
                                          "Salin kode"),
    ("ds160_copy_ok",                      "✅ 已复制到剪贴板",
                                          "✅ Copied to clipboard",
                                          "✅ Đã sao chép vào bộ nhớ tạm",
                                          "✅ Disalin ke papan klip"),
    ("ds160_copy_fail",                    "复制失败",
                                          "Copy failed",
                                          "Sao chép thất bại",
                                          "Gagal menyalin"),
    ("ds160_open_website_btn",             "🚀 立刻去 ceac.state.gov",
                                          "🚀 Go to ceac.state.gov now",
                                          "🚀 Đi đến ceac.state.gov ngay",
                                          "🚀 Buka ceac.state.gov sekarang"),
    ("ds160_open_website_hint",            "已在新标签页打开, 登录后插件自动激活",
                                          "Opened in a new tab — the extension activates after you sign in",
                                          "Đã mở tab mới — tiện ích kích hoạt sau khi bạn đăng nhập",
                                          "Sudah dibuka di tab baru — ekstensi aktif setelah Anda masuk"),
    ("ds160_rotate_btn",                   "↻ 重置",
                                          "↻ Rotate",
                                          "↻ Đặt lại",
                                          "↻ Atur ulang"),
    ("ds160_rotate_confirm",               "确定重置 code?\n\n旧 code 会立即失效 (已经复制到插件的也会变无效)。继续吗?",
                                          "Rotate this code?\n\nThe old code will be invalidated immediately (any extension still holding it will stop working). Continue?",
                                          "Đặt lại mã này?\n\nMã cũ sẽ bị vô hiệu ngay (tiện ích đang giữ mã cũ sẽ ngừng hoạt động). Tiếp tục?",
                                          "Atur ulang kode ini?\n\nKode lama langsung tidak berlaku (ekstensi yang masih memegang kode lama akan berhenti bekerja). Lanjutkan?"),
    ("ds160_rotate_ok",                    "✅ 已重置 — 复制新 code 去插件 redeem",
                                          "✅ Rotated — copy the new code and re-redeem in the extension",
                                          "✅ Đã đặt lại — sao chép mã mới và dùng lại trong tiện ích",
                                          "✅ Sudah di-reset — salin kode baru dan redeem lagi di ekstensi"),
    ("ds160_panel_hint_1",                 "复制 code → 打开 Chrome Htex 插件 → 粘贴 → Redeem → 打开 ceac.state.gov。",
                                          "Copy the code → open the Htex Chrome extension → paste → Redeem → open ceac.state.gov.",
                                          "Sao chép mã → mở tiện ích Htex Chrome → dán → Redeem → mở ceac.state.gov.",
                                          "Salin kode → buka ekstensi Chrome Htex → tempel → Redeem → buka ceac.state.gov."),
    ("ds160_panel_hint_2",                 "档案指纹",
                                          "Archive fingerprint",
                                          "Dấu vân tay hồ sơ",
                                          "Sidik jari arsip"),
    ("ds160_fingerprint_more",             "…",
                                          "…",
                                          "…",
                                          "…"),
    ("ds160_issued_at",                    "签发时间",
                                          "Issued at",
                                          "Thời điểm tạo",
                                          "Waktu dibuat"),
]


def _inject_keys(path: Path, lang_index: int) -> int:
    """Insert NEW_KEYS into the `orderdetail` block, right after `ext_download_started`.

    Returns the number of keys actually inserted.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    od = data.get("orderdetail")
    if not isinstance(od, dict):
        print(f"  ⚠️ no orderdetail block in {path.name} — skipping")
        return 0

    # Skip keys we already have (idempotent re-runs)
    inserted = 0
    for key, zh, en, vi, idk in NEW_KEYS:
        if key in od:
            continue
        translation = (zh, en, vi, idk)[lang_index]
        od[key] = translation
        inserted += 1

    # Stable write-back: dump the whole file again with the same formatting.
    # We deliberately use a simple dump here; any pre-commit i18n sort hook
    # will tidy keys alphabetically afterwards.
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return inserted


def main() -> int:
    files = [
        ("zh-CN.json", 0),
        ("en.json",    1),
        ("vi.json",    2),
        ("id.json",    3),
    ]
    total = 0
    for fname, idx in files:
        path = ROOT / fname
        if not path.exists():
            print(f"  ⚠️ missing {path} — skipping")
            continue
        n = _inject_keys(path, idx)
        print(f"  {fname}: +{n} keys")
        total += n
    print(f"Total: +{total} keys across {len(files)} languages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())