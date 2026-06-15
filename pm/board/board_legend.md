# W1 看板图例

> 跟 `pm/board/W1_board.md` 配套使用.

## 状态枚举

| 状态         | 含义                              | 流转                              |
| ------------ | --------------------------------- | --------------------------------- |
| `To Do`      | 未开始,本周要做的                  | `In Progress` / `Blocked`         |
| `In Progress`| 进行中(有 Owner + 进度条)          | `Done` / `Blocked`                |
| `Done`       | 本周内完成,产物有证据              | (本周内不再改状态)                |
| `Blocked`    | 卡住,等别人 / 外部依赖             | 解了 → 回到 `In Progress` 或 `Done` |

## 优先级

- **P0** - critical path,延期 1 天 → 上线延期(M8)
- **P1** - 重要但非 critical,可挪 2-3 天
- **P2** - nice-to-have,挪到下周或砍掉

## ID 规则

- `T-NNN` - 任务(To Do)
- `D-NNN` - 已完成
- `B-NNN` - 阻塞
- `R-NNN` - 风险(见 `pm/risks/risks.md`,本看板不重复)

## 流转规则

1. 任务创建 → `To Do`
2. Owner 开始 → `In Progress`(填开始日 + 进度%)
3. Owner 完成 → `Done`(填完成日 + 证据)
4. 卡住 → `Blocked`(填阻塞源 + 解法)
5. Blocked 解了 → 回 `In Progress` 或 `Done`

## 更新频率

- 站会后(每天 10:00)PM 滚一次
- 任务状态变了,owner 立即告诉 PM
- 每周五 17:00 收口 → 关 W 列,起下周列
