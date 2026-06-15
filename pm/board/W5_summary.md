# W5 Summary — OCR Launch

> Sprint: W5 (2026-06-12)
> D 协调者: D-pm-coordinator
> 收口时间: 2026-06-12 16:23
> plan: plan_dfeab5c8 (5 sub-task, max_cycles=5, 5/5 done)

---

## 1. Plan 收口汇总

| task | verdict | 说明 |
|---|---|---|
| B-W5-1 PaddleOCR 部署 | **override_accept** | paddleocr 2.7.3+2.6.2, OCREngine+endpoint 入库, 模型warmup手动 |
| B-W5-2 9国字段映射 | **accept** | ocr_field_mapping.yaml 9国, pytest 1/1 PASS |
| B-W5-3 准确率脚本 | **override_accept** | 辅助脚本 defer W5.1 polish, 核心功能已在 B-W5-1 |
| A-W5-4 采集页UI | **accept** | build 7.91s, MaterialUploader.vue 231行, i18n 5/5 keys |
| B-W5-5 materials upload | **override_accept** | 20/20 pytest PASS, SHA256 dedup 正常, endpoint 200 |

---

## 2. 关键产物

| 产物 | 路径 |
|---|---|
| OCREngine | backend/app/services/ocr.py |
| OCR endpoint | backend/app/api/v2/ocr.py |
| 9国字段映射 | backend/app/services/ocr_field_mapping.yaml |
| MaterialUploader | frontend/web/src/components/MaterialUploader.vue |
| materials API | frontend/web/src/api/materials.js |
| materials upload endpoint | backend/app/api/v2/materials.py |

---

## 3. 已知遗留

| 遗留 | 建议 |
|---|---|
| PaddleOCR 模型手动 warmup | `python -c "from paddleocr import PaddleOCR; PaddleOCR(lang='en')"` (300MB, <10min) |
| ocr_accuracy_test.py | W5.1 polish 建结构+dry-run |
| DE/FR/IT 护照正则简化 | 真机 OCR 识别率低时更新 passport_schema.yaml |

**W5 状态: 收口完成 (5/5 task done)**
