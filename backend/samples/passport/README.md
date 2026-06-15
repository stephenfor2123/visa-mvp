# Passport Sample Image Collection

**V2 §5.1.4 — 100 张样本护照图片验收目录**

本目录用于 OCR 准确率验收测试 (`tests/ocr_accuracy_test.py`)。

## 目录结构

```
samples/passport/
├── US/        # 美国 (United States) — 9位字母数字
├── JP/        # 日本 (Japan) — 2字母+7数字
├── GB/        # 英国 (United Kingdom) — 9位纯数字
├── AU/        # 澳大利亚 (Australia) — 2字母+7数字
├── SG/        # 新加坡 (Singapore) — 字母+7数字
├── DE/        # 德国 (Germany) — C/F 开头 + 7位
├── FR/        # 法国 (France) — C/F 开头 + 7位
├── IT/        # 意大利 (Italy) — C/F 开头 + 7位
└── KR/        # 韩国 (South Korea) — M/S 开头 + 7位
```

## 如何获取 100 张样本

> ⚠️ **注意**: 不要实际下载 100 张真实护照图片 — 涉及个人隐私数据。
> 以下方案在 W5 后半段实施：

### 推荐方案：合成数据集

使用护照模板生成工具合成逼真的测试图片：

1. **passport-photo-python** (GitHub):
   ```bash
   pip install passport-photo
   python -c "from passport_photo import PassportPhoto; ..."
   ```

2. **Biometrician Passport Generator** (开源):
   ```bash
   # ICAO 9303 规范合成
   python generate_passport.py --country US --count 10 --output US/
   ```

3. **Faker 库合成元数据 + PIL 生成图片**:
   ```python
   from PIL import Image, ImageDraw, ImageFont
   import random, string

   def synthetic_passport(country: str, out_path: str):
       # 渲染护照布局 (姓名/护照号/生日/有效期/国籍)
       # 保存为 JPEG 供 OCR 测试
   ```

### 替代方案：公开数据集

| 数据集 | 来源 | 许可 |
|--------|------|------|
| ICAO 9303 Test Cards | NIST (美国国家标准与技术研究院) | Public Domain |
| Multiple Biometrics Grand Challenge (MBGC) | NIST | 需申请 |
| WIDER Passport Detection | WIDER Challenge | 研究用途 |

### 各目录样本分配（建议）

| 国家 | 数量 | 护照格式 | 备注 |
|------|------|----------|------|
| US   | 12   | TD1, 9位字母数字 | 封面+资料页 |
| JP   | 12   | TD2, 2字母+7数字 | 日文姓名 |
| GB   | 12   | 9位纯数字        | 风格独特 |
| AU   | 10   | 2字母+7数字      | 与 DE/FR 格式相同 |
| SG   | 10   | 字母+7数字       | 首位字母 |
| DE   | 10   | C/F 开头+7位     | 德语姓名 |
| FR   | 10   | C/F 开头+7位     | 法语姓名 |
| IT   | 12   | C/F 开头+7位     | 意大利语姓名 |
| KR   | 12   | M/S 开头+7位     | 韩文姓名 |
| **合计** | **100** | | |

## 验收标准

| 里程碑 | 准确率要求 |
|--------|-----------|
| W3 (Launch) | ≥ 80% |
| W8 (GA)     | ≥ 95% |

运行测试:
```bash
# 80% 门槛
python tests/ocr_accuracy_test.py --sample-dir samples/passport --min-confidence 0.80

# 95% 门槛 (W8)
python tests/ocr_accuracy_test.py --sample-dir samples/passport --min-confidence 0.95
```

输出 `samples/passport/accuracy_results.csv` 包含每张图片的置信度与 PASS/FAIL 判定。

## 当前状态

- [ ] US/   — 0/12 张
- [ ] JP/   — 0/12 张
- [ ] GB/   — 0/12 张
- [ ] AU/   — 0/10 张
- [ ] SG/   — 0/10 张
- [ ] DE/   — 0/10 张
- [ ] FR/   — 0/10 张
- [ ] IT/   — 0/12 张
- [ ] KR/   — 0/12 张
- [ ] README.md (本文件)

**TODO (W5 后半段)**: 填充 100 张合成/公开样本，运行准确率测试，产出 `accuracy_results.csv`。