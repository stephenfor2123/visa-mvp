# 历史日志

> 本目录是 Htex 项目**历史 sprint / worklog / 决策记录**的归档。
> 2026-07-02 起,**唯一权威日志** = 项目根目录的 `ALL_WORKLOGS_MERGED.md`(W1 → W45 全量合并版,844 行 / 47 KB)。
> 后续所有变更、版本、Sprint 总结、决策记录只追加到 `ALL_WORKLOGS_MERGED.md`,**不再写新分文件**。

---

## 目录结构

```
历史日志/
├── README.md                     ← 本文件
├── CHANGELOG.md                  ← W1 → W32 历史版本日志(已被 ALL_WORKLOGS_MERGED.md §1 取代)
├── KNOWN_ISSUES.md               ← W45 端到端自测发现的 8 个待修 bug + 历史 pytest 副作用记录
├── board.md                      ← W5 OCR Launch 时的实时 board(已被 ALL_WORKLOGS_MERGED.md §4 取代)
├── A_WORKLOG.md                  ← A 前端 W6b + W8-2 + W9-1/W9-2 + W10-2 + W11c-1 + W13-cicd-2 段(摘自原 A_WORKLOG.md)
├── C_WORKLOG.md                  ← C verifier W6b → W11R Continuity 实战日志
├── WORKLOG.md                    ← D-pm-coordinator W1-W10 工作日志
├── WORKLOG.json                  ← D-pm-coordinator 结构化日志(W1-W10)
├── DASHBOARD.md                  ← D-pm-coordinator 项目管理 dashboard
├── pm-board/                     ← 各 Sprint 总结 + gate 报告 + roadmap
│   ├── W1_summary.md
│   ├── W1_board.md
│   ├── W1_gate_report.md
│   ├── W4_summary.md
│   ├── W5_summary.md
│   ├── W6b_gate_report.md
│   ├── W7_summary.md
│   ├── W7_gate_report.md
│   ├── W8_summary.md
│   ├── W8_gate_report.md
│   ├── W9_summary.md
│   ├── W9_gate_report.md
│   ├── W10_summary.md
│   ├── W10_gate_report.md
│   ├── W11_summary.md
│   ├── W11R-CONT_gate_report.md
│   ├── W14_summary.md
│   ├── W14_worklog.md
│   ├── W14_gate_report.md
│   ├── W15_roadmap.md
│   └── board_legend.md
```

---

## 使用规则

### ✅ 应该写

- **新版本/新 Sprint 完成后**:在 `ALL_WORKLOGS_MERGED.md` 顶部"版本时间线"表追加一行 + 在"完整改动记录"章节追加新 Sprint 段
- **新已知问题发现**:在 `ALL_WORKLOGS_MERGED.md` §3 追加条目(标 P0/P1/P2 + 来源)
- **新决策/新 rule**:在 `ALL_WORKLOGS_MERGED.md` §4 追加

### ❌ 不应该写

- ❌ 在本目录(`历史日志/`)新建 `W*_summary.md` / `W*_gate_report.md` / `*_WORKLOG.md` 文件
- ❌ 在根目录新建 `CHANGELOG.md` / `KNOWN_ISSUES.md` / `board.md` / `*_WORKLOG.md` — 这些都已归档
- ❌ 在 `pm/board/` 重建 W* 目录(该目录已删除,合并到本目录的 `pm-board/`)

### 🔍 回溯历史

如需查看某个 Sprint 详细 gate 报告 / 实战过程:
1. 优先看 `ALL_WORKLOGS_MERGED.md` 对应 W 段(已提取关键数字 + 关键决策 + 来源路径)
2. 需要原文细节 → 跳到本目录 `pm-board/W*_*.md` 看原始 gate report
3. 需要 A/B/C/D 某角色的逐次工作日志 → 看本目录 `A_WORKLOG.md` / `C_WORKLOG.md` / `pm/WORKLOG.md` 等

---

## 归档时间

**归档时间**: 2026-07-02 13:38 (Asia/Shanghai)
**归档操作**: mavis team / merge-worklogs → 后续 / organize-history
**原因**: 38 个分散的 worklog / summary / gate 报告文件已合并到 `ALL_WORKLOGS_MERGED.md`,为避免后续维护时多源不一致,统一以 ALL_WORKLOGS_MERGED.md 为唯一权威日志,本目录仅作历史回溯

---

## 不在本目录的"日志"类文件(说明)

以下文件虽然包含 sprint/worklog 关键词,但**不属于"工作日志归档"范围**,仍保留在原位置:

- **`pm/architecture/` `pm/risks/` `pm/wbs/` `pm/standup/` `pm/docs/` `pm/infra/`** — 项目管理子目录(架构图、风险登记、WBS 拆解、站会纪要、PM 文档、基础设施脚本),与工作日志性质不同
- **`backend/WORKLOG.md`** — 后端模块级技术日志(1409 行,记录每一次后端代码改动),与项目管理层的 sprint 总结不同
- **`A_WORKLOG.md.bak` `C_WORKLOG.md.bak` `DEMO-ACCOUNT.md.bak`** — 备份文件,不动
- **`outputs/*/deliverable.md`** — 单次任务的交付物,不属于"日志"性质(已合并到 ALL_WORKLOGS_MERGED.md §1 时间线锚点)
- **`.bak` 备份文件** — 备份文件,不动
