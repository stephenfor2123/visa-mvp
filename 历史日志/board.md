# 签证项目 — 实时 Board (Mavis 维护)

> **当前**: W5 OCR Launch (M3 milestone 启)
> **plan_id**: plan_5bb29103
> **owner**: D 协调者 mvs_ff58bd51b804435eafacd498ab74b355
> **update**: 2026-06-12 10:28

---

## 🎯 W5 OCR Launch — A/B/C 任务实时

### B 后端 (B)

| Task | 状态 | 进度 | Session |
|---|---|---|---|
| **B-W5-1** PaddleOCR 部署 + POST /ocr/recognize + 1 pytest | 🟢 **producing** | coder 在跑 | mvs_6b06cb1d... |
| **B-W5-2** 9 国护照字段映射 YAML + 1 pytest | 🔴 **verifier FAIL** | producer 漏写 test 文件, 等 cycle 2 retry | mvs_1c52471... |
| **B-W5-3** OCR 准确率验收脚本 + 100 张样本目录 | ⚪ **ready** (等 W5-1) | — | — |
| **B-W5-5** POST /materials/upload + SHA256 去重 + pytest | ⚪ **ready** (等 W5-1) | — | — |

### A 前端 (A)

| Task | 状态 | 进度 | Session |
|---|---|---|---|
| **A-W5-4** Materials.vue 上传组件 + i18n | ⚪ **ready** (等 W5-1) | — | — |

### C 测试 (C)

| Task | 状态 | 进度 | Session |
|---|---|---|---|
| 暂未排期 (等 A-W5-4 完) | — | — | — |

---

## 📊 W5 plan 统计

- **总 task**: 5
- **producing**: 1 (B-W5-1)
- **verifying**: 1 (B-W5-2 cycle 2 重试中)
- **ready**: 3 (B-W5-3 / A-W5-4 / B-W5-5)
- **cycle**: 1 → 2 (W5-2 retry)
- **WIP**: 2/3 (D cap)

---

## 🚦 关键节点 (M3 = W3 OCR 跑通)

- M3 milestone: 2026-07-03 (WBS W3 段)
- 距今: 21 天
- 当前进度: W5 launch 启, 5 sub-task 派活
- 风险: B-W5-1 PaddleOCR 装包 ~3min (网络依赖), B-W5-2 verifier FAIL 等 retry
- 决策: D-W5-001 已闭 (Mavis 10:20 拍板 "收官 W4 + 启 W5")

---

## 📝 上一个里程碑: W4 收官

- W4 polish-1b: plan_6f0c842b 09:18 PASS ✅
- W4 polish 1: plan_1e50de3b 09:03 cancelled (cycle 1 FAIL → cycle 2 用 plan_6f0c842b 替代)
- W4 polish-1c: plan_d5de84b7 08:58 PASS ✅
- 详见 pm/board/W4_summary.md

---

## 🐳 W13-cicd-2 — Docker buildx 多架构镜像 (2026-06-13 23:25)

| Task | 状态 | 进度 | 备注 |
|---|---|---|---|
| **W13-cicd-2** Dockerfile 多阶段 + .dockerignore + compose + buildx script | 🟢 **done** | 4 文件修整实战,sha256 全锁 | mvs_58b1d6b7... |

### 修整实战文件 (sha256)

- `backend/Dockerfile` — `1fbaa3b6697c55c57e559911b1bcde2a3c06e6df13f10cc4d67f7a0057a72180` (单阶段 31 行 → 多阶段 85 行,builder+runtime)
- `backend/.dockerignore` — `a54adb65b970719a2c0b8ba5387e57a4011c901b606a732e009630dfc1f60ea8` (新建 77 行,排除 .git/.env/__pycache__/data/等)
- `backend/docker-compose.yml` — `de635e25dfa4ddca9739c0125175e54555443b60387ddacc8d03e19483e6fc1f` (56 → 71 行,加 buildx 注释)
- `backend/scripts/build-multiarch.sh` — `864310a6e4b463f842b2756698eda2e02f0af0f4323bfcc1b16ecb5850f98a28` (新建 78 行,chmod +x)

### Fallback 触发 (D 必读)

- 本机 Intel x86_64 Mac (StephendeMacBook-Pro.local) 无 docker 运行时
- D prompt 写 "Apple silicon macOS" 与本 worker 实际环境不符
- buildx 实跑留到 CI runner (`.github/workflows/docker-publish.yml`)
