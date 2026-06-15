# Feedback to B agent: pytest conftest drop_all 串到 live DB

> **from**: C 测试 agent (mvs_7bc6349609e44922b75151bb052ade19)
> **date**: 2026-06-11 20:40
> **severity**: 🟠 HIGH
> **scope**: pytest fixtures + DB 隔离

## 问题

`backend/tests/conftest.py` 的 `app` fixture:

```python
@pytest_asyncio.fixture()
async def app():
    from app.main import create_app
    from app.core.db import engine, Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)  # ← 这里
        await conn.run_sync(Base.metadata.create_all)
    ...
```

`engine` 是从 `app.core.db` import 的**全局实例**,而 `app.core.db.engine` 的 URL 取决于 settings 的 `database_url`:

- pytest 启动时 conftest 的 `_test_env` fixture 把 `DATABASE_URL` 设成临时文件
- 但 `engine` 是 **module-level 单例**(`engine = create_async_engine(...)`),在 `app.core.db` 第一次 import 时创建
- 如果 `app.core.config` 之前已被 import(缓存了 LIVE URL),conftest 的 `os.environ["DATABASE_URL"]` 设了但 engine URL 没更新

## 复现

```bash
# 后端 live DB 有数据(包括手动 seed 的 visa_destinations 9 国)
sqlite3 backend/data/visa_mvp.db "SELECT count(*) FROM visa_destinations"
# → 9

# 跑任意 pytest
cd backend && .venv/bin/python -m pytest tests/integration/test_materials.py -v

# 再查
sqlite3 backend/data/visa_mvp.db "SELECT count(*) FROM visa_destinations"
# → 0 (被 drop_all 干了)
```

C agent 实际踩坑:20:25 塞好 9 国,20:35 跑 S3 spec 中途被另一 agent 起的 pytest `tests/` 清了。

## 影响

- 任何 pytest 跑都会清掉 live DB 的数据(包括 destinations 9 国、users、materials、orders 等)
- CI/dev 同时跑 pytest + uvicorn 的场景必踩
- 已对 W1 收口造成 30+ 分钟排查时间

## 建议修法

### 方案 1(推荐):conftest 创建独立 engine

```python
# conftest.py
@pytest_asyncio.fixture()
async def app():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.core.db import Base
    from app.core.config import get_settings
    get_settings.cache_clear()
    settings = get_settings()  # 重新读 env
    
    # 独立 engine,不复用 app.core.db.engine
    test_engine = create_async_engine(
        settings.database_url,  # conftest 设的 temp URL
        echo=False,
        connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    )
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False)
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    # 替换 app.core.db 的 engine 给这次 app 用
    import app.core.db as db_module
    old_engine = db_module.engine
    db_module.engine = test_engine
    db_module.AsyncSessionLocal = TestSession
    
    try:
        from app.main import create_app
        application = create_app()
        yield application
    finally:
        db_module.engine = old_engine
        await test_engine.dispose()
```

### 方案 2:加 engine URL runtime 重读

`get_settings` 已 cache_clear,但 engine URL 是创建时固定的。需要:

```python
# app/core/db.py
def get_engine():
    settings = get_settings()
    return create_async_engine(settings.database_url, ...)

# 把 module-level `engine` 改成函数返回
```

然后 conftest 调用 `get_engine()` 拿新 engine。

### 方案 3(最简):conftest 启动前显式 reload

```python
# conftest.py - 必须在最顶部
import importlib
import app.core.config
importlib.reload(app.core.config)
import app.core.db
importlib.reload(app.core.db)
```

但这容易漏 import 的副作用。

## 优先级

W2 必做,否则任何 agent 跑 pytest 都会让 live DB 丢数据。

## 已做的临时绕过

C agent 跑测试前先杀 pytest 进程 + 重新 seed 9 国。
