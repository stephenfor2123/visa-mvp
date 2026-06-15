# Feedback to B agent: destinations 9 国 seed 没自动跑

> **from**: C 测试 agent (mvs_7bc6349609e44922b75151bb052ade19)
> **date**: 2026-06-11 20:40
> **severity**: 🟠 HIGH
> **scope**: W1 S3 destinations 数据

## 问题

alembic 0002_destinations migration 升级后:
- ✅ `visa_destinations` 表建了
- ❌ 9 国 seed 数据的 INSERT 没生效
- `alembic_version` 直接更新到 `0002` (后续又被 `0003` / `0004` 覆盖)

实测:从 17:13 跑过 alembic 升级 → 表存在但 0 行,直到 20:25 C agent 手动塞 9 国才让 destinations API 返数据。

## 影响

- `/api/v2/destinations` 返 `data: []` → Destinations.vue 渲染空 → S3 E2E fail
- **任何刚跑完 alembic upgrade head 的环境** 都缺数据
- 每次 uvicorn 重启不会自动恢复(因为 seed 在 alembic,不在 lifespan)

## 复现

```bash
cd /Users/stephen/Desktop/签证项目/backend
.venv/bin/python -c "import sqlite3; c=sqlite3.connect('data/visa_mvp.db'); print('count:', c.execute('SELECT count(*) FROM visa_destinations').fetchone()[0])"
# → 0
```

## 建议修法(三选一,推荐 1)

### 方案 1:alembic 0002 拆 seed 到独立事务(Python 层)

```python
def upgrade() -> None:
    op.create_table("visa_destinations", ...)
    op.create_index(...)
    # seed 单独提交,不受 alembic 整体事务影响
    bind = op.get_bind()
    for d in DESTINATIONS:
        try:
            bind.execute(sa.text("INSERT INTO visa_destinations ..."), {...})
        except Exception:
            pass  # 重复 seed 跳过
    # 不返回
```

**关键**:alembic 升级是单事务,如果 seed 失败 + 后续语句失败,alembic 会回滚全部(包括表创建)。拆独立事务 / 用 savepoint 兜底。

### 方案 2:lifespan 启动时检查 + 自动 seed

`app/main.py` 的 `lifespan` 启动函数,加:

```python
from sqlalchemy import select, text
from app.models.destination import VisaDestination

async def lifespan(app):
    ...
    async with engine.begin() as conn:
        count = (await conn.execute(select(VisaDestination).limit(1))).scalar()
        if count is None:
            # 首次启动,seed 9 国
            for d in DESTINATIONS:
                await conn.execute(...)
```

### 方案 3:独立 seed 脚本 + README 说明

`backend/scripts/seed_destinations.py`,README 加"首次跑必须 `python scripts/seed_destinations.py`"。

## 优先级

W2 必做,否则每次 fresh DB 后 S3 E2E 都跑不通。

## 已做的临时绕过

C agent 在 `data/visa_mvp.db` 手动塞了 9 国,当前环境能跑 S3。**这是临时措施,B agent 接管后请按上面方案正式修。**
