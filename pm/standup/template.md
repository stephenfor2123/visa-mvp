# Standup 模板 · 每日填写

> **何时填**:每天 9:30 之前(站会前 30min)
> **写给谁**:PM (D) + 跨 agent(同侪)
> **格式**:Markdown,粘贴到对应角色 daily file
> **总时长**:每个 agent 写 5min,PM 5min 汇总 → 站会 9:45 - 10:00(15min)

---

## 单人 daily file 格式(每个 agent 复制一份)

```markdown
## W{W} · D{D} · {YYYY-MM-DD} · {角色}

**Agent**: {frontend-A / frontend-B / backend-A / qa-A / pm-D / ...}
**今/昨日天气**: ☀️ / 🌧(心情指数,可选)

### ✅ 昨日完成
- [具体可验证的产出,带文件路径 / 链接 / commit]
  - 例:`frontend/web/src/views/login.vue` 完成 + 截图
- [PR / 截图 / 文档 链接]

### 🎯 今日计划
- [ ] 任务 1(具体到交付物)
- [ ] 任务 2
- [ ] 任务 3

### 🚧 阻塞 / 需要帮助
- 阻塞 1:{谁卡了你} → {要谁做什么} → {卡多久了}
- 风险:{可能延期或质量下降}
- 或写"无"

### 📊 数据(可选,QA / 后端填)
- 测试用例:+N 条 / 总 N 条 / 覆盖率 X%
- API 端点:已完成 N/总 N
- LOC:+N / 累计 N

### 💡 学到 / 想到(可选)
- 任何工艺 / 工具 / 设计上的小洞察,沉淀到 WIKI
```

---

## PM 汇总格式(每天 10:00 站会后,PM 输出到 `pm/standup/summary_YYYYMMDD.md`)

```markdown
## {YYYY-MM-DD} · 站会纪要

**参会**: A / B / C / D(谁缺席请注明)
**总时长**: 15 min

### 进度
- Frontend: 进度 X/10, 在做 X
- Backend: ...
- QA: ...
- AI&RPA: ...
- PM: ...

### 🚨 阻塞升级
- 阻塞 1:{描述} → {谁接} → {预计解决时间}
- 或写"无"

### 🎯 今日 cross-team 配合
- A 等 B: {任务}
- B 等 A: {任务}

### 📊 关键指标
- 完成 story point: X(本周累计 Y)
- 测试覆盖率: X%
- 阻塞累计时长: X 小时(本周)

### 下次站会
- 明日 9:45
- 重点关注: {1-2 个}
```

---

## Standup 流程(PM 主理)

1. **9:30 前** - 所有 agent 把 daily 写完
2. **9:30 - 9:45** - PM 收集,扫一眼阻塞
3. **9:45 - 10:00** - 站会(15min),每人 1-2min
   - 格式:昨日 / 今日 / 阻塞
4. **10:00 - 10:15** - PM 输出 `summary_YYYYMMDD.md`,同步给所有人
5. **每周五 10:00 - 10:30** - 风险评审(过 12 条)

---

## 链接

- [frontend daily](./frontend.md)
- [backend daily](./backend.md)
- [qa daily](./qa.md)
- [pm daily](./pm.md)
- [ai_rpa daily(bonus)](./ai_rpa.md) — 任务规范外,项目管理需要
