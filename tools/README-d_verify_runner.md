# D-VERIFY-RUNNER 1.0

自动化 7 步 DoD 验证工具 — D Coordinator plan handoff 质量门。

## 快速开始

```bash
cd /Users/stephen/Desktop/签证项目
python tools/d_verify_runner.py --task-id C-W11R-3 --verbose
python tools/d_verify_runner.py --task-id B-W7-1 --json
```

## 7 步检查

| Step | 检查项 | 失败原因 |
|------|--------|----------|
| 1 | 截图 sha256 唯一 | 同一截图文件出现两次（同名覆盖/复制错误） |
| 2 | deliverable.md > 50 bytes | 文件不存在/为空/少于 10 行 |
| 3 | WORKLOG.md 含 task-id | producer 未记录 WORKLOG |
| 4 | backend pytest 全 PASS | 测试失败或超时 |
| 5 | alembic upgrade head --dry-run | 数据库迁移不兼容 |
| 6 | i18n 无 raw key | dist/assets/*.js 含未解析的 i18n key（如 `home.features.title`） |
| 7 | .env / config.yaml 可读 | 配置文件不存在或无读权限 |

## 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--task-id` | **必需** | 任务 ID，如 `C-W11R-3` |
| `--screenshots-dir` | `outputs/<task-id>/screenshots` | 截图目录 |
| `--deliverable-path` | `outputs/<task-id>/deliverable.md` | deliverable 路径 |
| `--worklog-path` | `workspace/backend/WORKLOG.md` | WORKLOG 路径 |
| `--pytest-target` | `tests/integration/test_payment_stripe_stub.py` | pytest 目标文件 |
| `--frontend-dist` | `frontend/web/dist` | 前端构建产物目录 |
| `--project-root` | 自动检测 | 项目根目录 |
| `--min-bytes` | 50 | deliverable 最小字节数 |
| `--min-lines` | 10 | deliverable 最小行数 |
| `--json` | False | JSON 格式输出 |
| `--verbose` / `-v` | False | 详细输出 |

## 退出码

```
0  全部 7 步 PASS
1  Step 1 FAIL (截图 sha256 碰撞)
2  Step 2 FAIL (deliverable 不合规)
3  Step 3 FAIL (WORKLOG 未记录)
4  Step 4 FAIL (pytest 失败)
5  Step 5 FAIL (alembic 迁移错误)
6  Step 6 FAIL (i18n raw key 残留)
7  Step 7 FAIL (.env/config 不可读)
8  参数错误
```

## Step 6 i18n raw key 检测策略

在 `dist/assets/*.js` 中用正则匹配 i18n key root（`home.` / `auth.` / `common.` / `order.` 等），排除：
- URL 路径中的同名字符串（如 `/api/home`）
- JSON 值中的 key（已被 vue-i18n 解析）
- 注释中的字符串

> **注意**：Step 6 是启发式检测，可能有漏报/误报。如需精确验证，请用 Playwright E2E 截图检查页面文案。

## Step 5 alembic dry-run

使用 `--dry-run` 参数，仅验证迁移脚本语法，不实际执行。避免对开发数据库造成破坏。

## 设计原则

- **零依赖**：仅用 Python 3 标准库，无第三方包
- **幂等**：可重复运行，结果一致
- **自描述**：exit code + human-readable output 双通道
- **Skip 友好**：截图/前端不存在时自动跳过对应 Step，不阻断其他检查