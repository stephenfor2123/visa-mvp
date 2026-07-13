# Sprint 迭代 / 发版索引

本目录记录**按天迭代**的待发版内容，与 git **一天一个 commit** 的节奏对齐。

## 规则

### 1. 一天一个 commit

- 每个自然日（或你选定的一个发版日）对应 **一个** git commit，不拆成多个小 commit（除非当天明确标注「hotfix 例外」）。
- 当天所有要上线的功能、修复、文档，都写进同一天的 `YYYY-MM-DD.md`，发版前核对清单再一次性 `git add` + `commit`。

### 2. 文件命名

| 文件 | 用途 |
|------|------|
| `README.md` | 本规则说明 |
| `INDEX.md` | 总索引：日期 → 状态 → commit hash → 摘要 |
| `YYYY-MM-DD.md` | 当日待发版明细（功能、文件、迁移、部署步骤） |

### 3. 每日 md 建议结构

```markdown
# YYYY-MM-DD

## 状态
draft | ready | committed | deployed

## 建议 commit message
一行英文或中文，动词开头

## 功能清单
- [ ] 功能 A
- [ ] 功能 B

## 数据库 / 迁移
- alembic upgrade …

## 部署后验证
- [ ] 检查项

## 变更文件（摘要）
按模块列路径，新文件标 (new)

## 不纳入本次 commit
截图、本地调试产物等
```

### 4. 状态流转

```
draft → ready → committed → deployed
```

| 状态 | 含义 |
|------|------|
| `draft` | 开发中，条目可增删 |
| `ready` | 清单已定，可执行 commit |
| `committed` | 已 commit，在 INDEX 填 hash |
| `deployed` | 已上生产并验证 |

### 5. 发版日流程（Checklist）

1. 打开当天 `YYYY-MM-DD.md`，勾完功能清单。
2. `git status` 与文档「变更文件」对齐；无关文件不要 `git add`。
3. 跑迁移 / 测试（文档里写的必跑项）。
4. 一个 commit，message 用文档「建议 commit message」。
5. 更新 `INDEX.md`：状态 → `committed`，填 hash。
6. 部署后：状态 → `deployed`，补验证结果。

### 6. 不要 commit 的内容

- `.env`、密钥、Stripe secret
- 根目录 `*.png` 截图、预览 html（除非产品明确要求入库）
- `browser-extension/*.zip` 构建产物（源在 extension 目录即可）

### 7. 与历史文档的关系

- `docs/TASKS_COMPLETION.md`、`docs/PRE_LAUNCH_OWNER_TODO.md`：长期任务跟踪。
- **`docs/sprint/`**：**短期、按天、可发版**的索引；发版以这里为准。
