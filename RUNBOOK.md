# Visa MVP — 运维事故手册 (RUNBOOK)

> **面向对象**: 一线 on-call 工程师 / SRE / 二次值班 TL  
> **适用范围**: Visa MVP API V2 + Celery worker + 前端 Web 静态站点  
> **环境基线**: FastAPI (uvicorn) + Async SQLAlchemy 2.0 + Redis (Celery broker/result) + SQLite/Postgres  
> **首次发布**: 2026-06-15 / Mavis W16 阶段  
> **更新规则**: 每次 P0/P1 事故复盘后必须更新对应章节；至少每季度 review 一次  

---

## 0. 30 秒速查 (TL;DR)

| 事故类型 | 一句话定位 | 翻到 |
|---|---|---|
| API 5xx 飙升 | `curl /health` → 看 `app.log` | §1 |
| DB 连接耗尽 | `engine.pool` + `visa.db` 大小 | §2 |
| Redis / Celery 挂 | `redis-cli ping` + `celery -A ... inspect` | §3 |
| RPA 任务卡死 | `rpa_tasks.py` status + 队列长度 | §4 |
| 支付失败 / 回调 5xx | `payment/notify` 日志 + WebhookEvent 表 | §5 |
| 登录失败 / 验证码错 | `auth_service` 日志 + SMS 发送记录 | §6 |
| 磁盘满 | `du -sh data/ uploads/ logs/` | §7 |
| 内存 / 进程泄漏 | `ps aux | grep uvicorn` + RSS 趋势 | §8 |

**核心服务端口**:

| 服务 | 端口 | 备注 |
|---|---|---|
| FastAPI (uvicorn) | 8000 | API + `/health` + `/metrics` |
| Redis | 6379 | Celery broker (db=0) + result backend (db=1) |
| Celery worker | — | 独立进程, 启动见 §3 |
| 前端 (Vite preview) | 4173 | `pnpm preview` |

**关键路径**:

```
/Users/apple/Desktop/签证项目/
├── backend/                # FastAPI + Celery
│   ├── app/main.py         # /health 在 :130
│   ├── app/celery_app.py   # broker = redis://localhost:6379/0
│   ├── data/visa_mvp.db    # SQLite (dev) / data/ 整体须 < 5 GB
│   ├── data/materials/     # 用户上传资料 (增长快!)
│   ├── logs/app.log        # 主日志 (按天轮转)
│   ├── logs/sms.log        # SMS 验证码审计
│   └── .env                # SECRET_KEY / DB URL / Redis URL
└── frontend/web/           # 静态前端
```

---

## 1. 事故: API 5xx 飙升

### 症状
- 监控告警: 5xx 比例 > 1% (持续 2 分钟)
- 用户反馈: 页面白屏 / "系统繁忙" / 接口超时
- `/health` 返回 `"status": "degraded"` 或 500

### 排错命令
```bash
# 1. 立即探测健康度
curl -sS http://localhost:8000/health | jq .
# 期望: {"status":"ok","db_ok":true,"version":"..."}
# 异常: "db_ok":false → 翻到 §2 (DB)
# 异常: 返回 5xx → 主进程挂了, 见下方 "进程存活"

# 2. 进程是否还活着
ps aux | grep -E "uvicorn|app.main" | grep -v grep
# 期望: 至少 1 个 uvicorn 进程, RSS < 1.5GB
# 异常: 0 个进程 → 进程崩了, 见 "缓解 1"

# 3. 最近错误日志
tail -n 200 /Users/apple/Desktop/签证项目/backend/logs/app.log \
  | grep -E "ERROR|Traceback|500|Exception" | tail -n 50

# 4. Prometheus 指标 (如果部署了)
curl -sS http://localhost:8000/metrics | grep -E "http_5xx|request_duration"
```

### 临时缓解
1. **进程崩了** → 立即拉起:  
   `cd /Users/apple/Desktop/签证项目/backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 &`  
   拉起后立刻同步到告警群, 让用户重试。
2. **5xx 是偶发 (DB 抖动 / 慢查询)** → 重启 worker:  
   `pkill -f "uvicorn app.main" && sleep 2 && nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 > logs/uvicorn.out 2>&1 &`
3. **限流 (防雪崩)** → 临时调小 `RATE_LIMIT_PER_IP_PER_MIN` (`.env`), 从 100 改成 30:  
   `sed -i.bak 's/^RATE_LIMIT_PER_IP_PER_MIN=.*/RATE_LIMIT_PER_IP_PER_MIN=30/' .env && pkill -f "uvicorn app.main" && 重新拉起`
4. **降级** → 关闭非核心端点: 在 `app/api/v2/__init__.py` 注释掉 `materials` / `ocr` / `voice` 等非关键 router 后重启。

### 根因修复
- **N+1 查询**: 找 `app.log` 里的 `sqlalchemy.exc` + `selectinload` 缺失。补 `.options(selectinload(...))`。
- **未捕获异常**: 任何 traceback 都要补 `try/except` + `BizException` (见 `app/core/errors.py`)。
- **超时配置**: uvicorn `--timeout-keep-alive 5` + 反代 `proxy_read_timeout 30`。
- **资源耗尽**: 见 §2/§7/§8。

---

## 2. 事故: DB 连接耗尽 / DB 不可达

### 症状
- `/health` 返回 `"db_ok": false` 或 5xx
- 日志频繁报: `sqlalchemy.exc.TimeoutError: QueuePool limit ... reached`
- 接口 P99 > 5s

### 排错命令
```bash
# 1. DB 文件是否存在 / 权限
ls -la /Users/apple/Desktop/签证项目/backend/data/visa_mvp.db
# 期望: 大小 < 2GB, owner = 当前用户
# 异常: 文件不存在 → 见 "缓解 1"; > 2GB → §7

# 2. SQLite 健康
sqlite3 /Users/apple/Desktop/签证项目/backend/data/visa_mvp.db "PRAGMA integrity_check;"
# 期望: ok
# 异常: database disk image is malformed → 立即停止写入, 见 "缓解 2"

# 3. 进程连接数 (Postgres 才有意义, SQLite 看 file lock)
lsof /Users/apple/Desktop/签证项目/backend/data/visa_mvp.db 2>/dev/null | wc -l
# SQLite: > 5 个 reader 是异常 (write lock 串行)

# 4. 长事务 / 慢查询
grep -E "slow query|elapsed [0-9]{3,}ms" /Users/apple/Desktop/签证项目/backend/logs/app.log | tail -20

# 5. 引擎 pool 状态 (在 Python REPL)
cd /Users/apple/Desktop/签证项目/backend && .venv/bin/python -c "
from app.core.db import engine
pool = engine.pool
print('size:', pool.size(), 'checkedout:', pool.checkedout(), 'overflow:', pool.overflow())
"
```

### 临时缓解
1. **DB 文件丢失** → 立即停服, 从备份恢复:  
   `cd /Users/apple/Desktop/签证项目/backend && .venv/bin/python scripts/restore.py --latest`  
   (前提: 有每日 backup, 见 `scripts/backup.py`)
2. **SQLite corrupted** → 用 `.backup` 命令导出可读数据:  
   `sqlite3 visa_mvp.db ".backup visa_mvp_rescue.db"` 然后排查; 仍坏就 `restore.py`。
3. **连接池打满 (Postgres 场景)** → 重启 API 进程, 临时改 `DATABASE_URL` 加 `?pool_size=20&max_overflow=10`。
4. **降级写** → 把 `materials.py` / `orders.py` 写操作切到异步队列, 缓解写锁竞争。

### 根因修复
- 任何长事务 (`with engine.begin()` 跨多请求) 必须改成短事务。
- 加 `pool_pre_ping=True` 到 `create_async_engine` (避免 stale connection)。
- 生产从 SQLite 迁到 Postgres: `DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/visa`。
- 加监控: Prometheus `sqlalchemy_pool_size` / `sqlalchemy_pool_checkedout`。

---

## 3. 事故: Redis 挂 / Celery 队列积压

### 症状
- Celery worker 启动失败: `redis.exceptions.ConnectionError`
- 用户提交订单后, RPA 任务一直 `submitting` 不前进
- `rpa.submit_visa_application` 在 broker 里堆积

### 排错命令
```bash
# 1. Redis 是否活着
redis-cli ping
# 期望: PONG
# 异常: Connection refused → 启动 redis-server

# 2. Redis 内存
redis-cli info memory | grep -E "used_memory_human|maxmemory_human"
# 期望: used < 80% of maxmemory
# 异常: 接近 maxmemory → 触发 LRU 淘汰, 见 "缓解 2"

# 3. 队列长度
redis-cli -n 0 llen celery
# celery broker 在 db=0
# 期望: < 100
# 异常: > 1000 → worker 拉取慢, 见 "缓解 3"

# 4. Celery worker 状态
cd /Users/apple/Desktop/签证项目/backend && \
  .venv/bin/celery -A app.celery_app inspect active
.venv/bin/celery -A app.celery_app inspect registered
# 期望: 至少 1 个 worker online, 注册了 rpa.submit_visa_application / rpa.check_rpa_status
# 异常: 0 online → 拉起 worker (见 "缓解 1")

# 5. worker 日志
ls -la /Users/apple/Desktop/签证项目/backend/logs/celery*.log 2>/dev/null
tail -n 100 <最新 celery worker log>
```

### 临时缓解
1. **Redis 没起** → 拉起:  
   `brew services start redis` (macOS dev) / `systemctl start redis-server` (Linux prod)  
   拉起后 `redis-cli ping` 确认 PONG。
2. **Redis 内存爆** → 清过期 key 或扩内存:  
   `redis-cli FLUSHDB` (会丢未完成任务, **慎用**) / `redis-cli --scan --pattern '*' | xargs -L 100 redis-cli del`  
   优先 `CONFIG SET maxmemory 2gb` 临时扩。
3. **worker 没拉任务** → 重启 worker:  
   `pkill -f "celery.*worker" && sleep 2 && nohup .venv/bin/celery -A app.celery_app worker --loglevel=INFO --concurrency=4 > logs/celery-worker.out 2>&1 &`
4. **任务长期 stuck** → 清队列 (仅紧急):  
   `redis-cli -n 0 DEL celery`  (丢所有未执行任务, **需要 TL 授权**)

### 根因修复
- 给 Redis 加监控: `redis_exporter` (Prometheus) + `used_memory > 80%` 告警。
- 任务里加超时 (Celery `task_time_limit=600` 10min)。
- 把 broker 从 Redis 迁到 RabbitMQ (W2.1+ 再评估)。

---

## 4. 事故: RPA 任务卡死

### 症状
- 用户提交订单后, 任务状态一直是 `submitting` / `waiting` 超过 30 分钟
- 确认号 (`confirmation_no`) 一直为空
- Celery worker 日志: `rpa.submit_visa_application` 多次重试, 全部失败

### 排错命令
```bash
# 1. 单个任务状态 (需要 task_id, 来自订单详情)
cd /Users/apple/Desktop/签证项目/backend && .venv/bin/python -c "
from app.api.v2.rpa import get_scheduler
s = get_scheduler()
print(s.get_task_status('rpa-xxxxxxxxxxxx'))
"
# 看 status / progress / message / error_detail

# 2. 全局在飞任务
.venv/bin/python -c "
from app.api.v2.rpa import get_scheduler
s = get_scheduler()
for t in s.list_tasks():
    if t['status'] in ('submitting','waiting'):
        print(t)
"

# 3. Celery 任务执行历史
.venv/bin/celery -A app.celery_app result <task_id>
# 期望: SUCCESS + 返回值
# 异常: PENDING 永久 → broker 丢消息; FAILURE → 看 traceback

# 4. RPA provider 上游连通性
curl -sS -o /dev/null -w "%{http_code}\n" https://evisa.imigrasi.go.id  # 印尼
curl -sS -o /dev/null -w "%{http_code}\n" https://evisa.xuatnhapcanh.gov.vn  # 越南

# 5. CAPTCHA solver 是否正常
grep -E "captcha|CAPTCHA" /Users/apple/Desktop/签证项目/backend/logs/app.log | tail -20
```

### 临时缓解
1. **上游不可达** → 在 `data/rpa_config.yaml` 把对应国家 `enabled: false`, 暂停该国家接单, 通知用户。
2. **CAPTCHA solver 失败** → 调高 `captcha_max_retries` (默认 3 → 5), 重启 worker。
3. **单个用户卡死** → 取消任务:  
   `.venv/bin/python -c "from app.api.v2.rpa import get_scheduler; s = get_scheduler(); print(s.cancel_task('rpa-xxxxx'))"`
4. **批量回滚** → 找到 `RPAScheduler` 的 `self._tasks` 内存 dict, 把 `submitting` 超 1h 的全部 `mark_failed` (写一次性脚本)。

### 根因修复
- 任务里加 `provider.fetch_form() with timeout=30`, 防止无限 hang。
- CAPTCHA solver 接入降级 provider (W2.1 评估, e.g. 2Captcha → Anti-Captcha 兜底)。
- 把 `_tasks` 内存 dict 持久化到 Redis (production 必须改, 见 `RPAScheduler` 注释)。

---

## 5. 事故: 支付失败 / 回调 5xx

### 症状
- 用户支付成功但订单状态卡在 `pending`
- `/api/v2/payment/notify` 返回 500
- 前端轮询 `/payment/{order_no}` 一直 `pending` 超 60s

### 排错命令
```bash
# 1. 最近 notify 回调日志
grep -E "payment/notify|NotifyPayment|Stripe-Signature" \
  /Users/apple/Desktop/签证项目/backend/logs/app.log | tail -50

# 2. WebhookEvent 表 (签名验签失败的会写表)
cd /Users/apple/Desktop/签证项目/backend && \
  .venv/bin/python -c "
import asyncio
from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.models.webhook_event import WebhookEvent
async def main():
    async with AsyncSessionLocal() as s:
        rs = await s.execute(select(WebhookEvent).order_by(WebhookEvent.id.desc()).limit(20))
        for r in rs.scalars():
            print(r.id, r.event_type, r.status, r.received_at, r.last_error)
asyncio.run(main())
"

# 3. 订单当前支付状态
.venv/bin/python -c "
import asyncio
from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.models.order import Order
async def main():
    async with AsyncSessionLocal() as s:
        o = await s.scalar(select(Order).where(Order.order_no == 'ORD-XXXXX'))
        print(o.order_no, o.payment_status, o.trade_no, o.paid_at)
asyncio.run(main())
"

# 4. mock 通道 1s 自动回调是否触发
grep "Mock auto-notify" /Users/apple/Desktop/签证项目/backend/logs/app.log | tail -10

# 5. Stripe 通道 (V2.1 才有) — webhook 验签失败
grep -E "Invalid signature|No signatures found" /Users/apple/Desktop/签证项目/backend/logs/app.log | tail -20
```

### 临时缓解
1. **单笔订单没收到回调** → 手动重放 (mock 通道, 见 `MockPaymentProvider.auto_notify`):  
   `.venv/bin/python -c "from app.services.payment.mock import MockPaymentProvider; import asyncio; asyncio.run(MockPaymentProvider().auto_notify('ORD-XXXXX'))"`
2. **notify 5xx 雪崩** → 暂时关闭 V2.1 Stripe 通道 (`.env` 留空 `STRIPE_SECRET_KEY=`, 强制走 mock):  
   `sed -i.bak 's/^STRIPE_SECRET_KEY=.*/STRIPE_SECRET_KEY=/' .env && 重启 uvicorn`
3. **WebhookEvent 表 stuck** → 写一次性脚本, 把 `status=failed` 超过 1h 的改成 `status=dead` + 走人工对账。
4. **签名验签失败** → 检查 `STRIPE_WEBHOOK_SECRET` 是否和 Stripe Dashboard 一致; 时钟偏差 `ntpdate -q pool.ntp.org`。

### 根因修复
- notify handler 加幂等: `INSERT ... ON CONFLICT (trade_no) DO NOTHING`。
- 加 `Stripe-Signature` 失败重试 3 次 (Celery delay, 1s/5s/30s)。
- 把 `WebhookEvent` 表加索引 `(event_id, status)`, 加速幂等查。
- 对账任务 (cron daily 02:00) 拉 Stripe API `/v1/charges?created[gte]=...` 跟本地对账。

---

## 6. 事故: 登录失败 / 验证码错

### 症状
- 用户报"验证码错误" / "密码错误" 比例 > 5%
- 短信发送失败 (sms.log 有 5xx)
- 登录 401 / 403 比例飙升

### 排错命令
```bash
# 1. SMS 发送审计
tail -n 100 /Users/apple/Desktop/签证项目/backend/logs/sms.log
# 看 send_code / verify_code 调用记录

# 2. 鉴权失败统计
grep -E "401|UNAUTHORIZED|FORBIDDEN" \
  /Users/apple/Desktop/签证项目/backend/logs/app.log | tail -30

# 3. JWT 解码是否正常
cd /Users/apple/Desktop/签证项目/backend && .venv/bin/python -c "
from app.core.security import decode_token
print(decode_token('<从浏览器复制 access_token>'))
"

# 4. SMS provider 是否可达 (mock 永远通, twilio/aliyun 看上游)
curl -sS -o /dev/null -w "%{http_code}\n" https://api.twilio.com  # twilio
curl -sS -o /dev/null -w "%{http_code}\n" https://dysmsapi.aliyuncs.com  # 阿里云

# 5. rate-limit 是不是误伤
grep "429" /Users/apple/Desktop/签证项目/backend/logs/app.log | tail -20
# auth 端点限流 60 req/min/IP (见 middleware/rate_limit.py:47)
```

### 临时缓解
1. **SMS 通道挂** → 切到 mock:  
   `.env` 加 `SMS_CHANNEL=mock` + `MOCK_SMS_WEBHOOK_URL=http://localhost:8000/api/v2/sms/mock-webhook`, 重启。  
   (mock 通道会把验证码打到 `logs/sms.log` 供人工查)
2. **JWT 过期集中爆发** → 临时拉长 TTL:  
   `sed -i.bak 's/^ACCESS_TOKEN_TTL_MINUTES=.*/ACCESS_TOKEN_TTL_MINUTES=480/' .env` (2h → 8h)
3. **限流误伤** → 临时调高: `RATE_LIMIT_SLOW_API_PER_IP_PER_MIN=120` (60 → 120)
4. **密码策略拒绝** → 临时放宽 (仅紧急, **必须事后回滚**): `BCRYPT_COST=8` (12 → 8) 加速 hash

### 根因修复
- SMS 加失败重试 3 次 (mock 通道不需要, 真实通道必须)。
- 密码 bcrypt cost: dev=8, prod=12 (`Settings.bcrypt_cost`)。
- JWT secret 必须 ≥ 32 bytes, 生产检查 `JWT_SECRET` 不等于 dev 默认值 (启动时 lifespan 会校验, 见 `app/main.py:50`)。
- 登录失败 5 次/15min 触发账号临时锁定 (W2.1 评估)。

---

## 7. 事故: 磁盘满

### 症状
- 上传资料 500 错误: `No space left on device`
- DB 写入失败
- 日志写入停摆, 无法定位问题

### 排错命令
```bash
# 1. 整盘空间
df -h /Users/apple/Desktop/签证项目/
# 期望: Use% < 80%
# 异常: > 90% → 见 "缓解 1"

# 2. 谁占的
du -sh /Users/apple/Desktop/签证项目/backend/data/*
du -sh /Users/apple/Desktop/签证项目/backend/logs/*
du -sh /Users/apple/Desktop/签证项目/backend/data/materials/* 2>/dev/null | sort -rh | head -10
# 重点关注: materials/ (用户上传) + logs/ (没轮转的话会很大)

# 3. 旧日志 (没轮转的项目常见)
ls -lhS /Users/apple/Desktop/签证项目/backend/logs/ | head -20

# 4. 大文件 (前 20)
find /Users/apple/Desktop/签证项目/backend/data -type f -size +100M \
  -exec ls -lh {} \; 2>/dev/null | sort -k5 -rh | head -20
```

### 临时缓解
1. **< 5% 剩余** → 立即扩盘 (云厂商) 或清临时文件:  
   `find /tmp -type f -size +50M -mtime +1 -delete`  
   `docker system prune -af` (如果是容器)
2. **materials/ 太大** → 把超过 90 天的归档到冷存储:  
   `find backend/data/materials -type f -mtime +90 -exec mv {} /Volumes/cold-storage/materials/ \;`  
   (V2 没冷存储就先 `gzip` 压缩: `gzip -9 {}`)
3. **logs/ 太大** → 强制轮转:  
   `find backend/logs -name "app.log.*" -mtime +30 -delete`  
   长期方案: 用 `logrotate` (见 "根因修复")。
4. **SQLite DB 太大** → VACUUM:  
   `sqlite3 backend/data/visa_mvp.db "VACUUM;"`  
   长期: 迁 Postgres (见 §2 根因修复)。

### 根因修复
- 加 `logrotate` 规则 (Linux):  
  ```
  /Users/apple/Desktop/签证项目/backend/logs/*.log {
      daily
      rotate 7
      compress
      missingok
      notifempty
      copytruncate
  }
  ```
- macOS dev: 写一个 launchd plist 每天跑 `newsyslog`。
- 资料加 lifecycle: 上传 30 天后归档, 90 天后清 (合规要求见 SECURITY.md)。
- 监控: `node_filesystem_avail_bytes` < 10% 告警。

---

## 8. 事故: 内存 / 进程泄漏

### 症状
- 单进程 RSS 持续上涨, 1h 内从 500MB → 2GB
- 触发 OOM Killer, 进程被 kill
- 接口响应越来越慢 (GC 频繁)

### 排错命令
```bash
# 1. 进程 RSS 排名
ps aux -o pid,rss,vsz,command | grep -E "uvicorn|celery" | grep -v grep | sort -k2 -rh
# 期望: 单 worker < 1.5GB
# 异常: > 2GB → 见 "缓解 1"

# 2. 内存趋势 (如果装了 node_exporter / prom-client)
curl -sS http://localhost:8000/metrics | grep process_resident_memory_bytes

# 3. 对象引用 / 缓存大小
# Python 进程:
cd /Users/apple/Desktop/签证项目/backend && .venv/bin/python -c "
import tracemalloc
tracemalloc.start()
# ... reproduce ...
snap = tracemalloc.take_snapshot()
for stat in snap.statistics('lineno')[:10]:
    print(stat)
"

# 4. 日志看是否有 OOM
dmesg | grep -i "out of memory"  # Linux
log show --predicate 'eventMessage contains "jetsam"' --last 1h  # macOS

# 5. celery worker 内存
ps aux | grep "celery.*worker" | grep -v grep | awk '{print $2, $6}'
```

### 临时缓解
1. **单进程 RSS > 2GB** → 立即重启:  
   `pkill -f "uvicorn app.main" && sleep 2 && nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 > logs/uvicorn.out 2>&1 &`
2. **加 worker 数均摊** → `--workers 4` (CPU 核数限制内), 配合 uvicorn `--loop uvloop` 提升吞吐。
3. **加 memory limit** (容器场景): docker-compose `deploy.resources.limits.memory: 1G` + `restart: on-failure`。
4. **rate-limit middleware 缓存膨胀** → 临时加清理: `RateLimitMiddleware.limiter._buckets.clear()` (需写一次性脚本注入)。

### 根因修复
- 找引用循环: `mprof run uvicorn app.main:app` + `mprof plot` 看内存曲线。
- 缓存加 LRU 边界: 任何 `@lru_cache` 必须 `maxsize=`, 全局 dict 必须定期清理 (例如 RPAScheduler 的 `_tasks` 应该有 TTL, 现状是 in-memory dict 无清理, 见 `app/services/rpa/rpa_scheduler.py:101`)。
- 大文件用 streaming 响应, 不要 `await file.read()` 一次性读内存。
- 监控: `process_resident_memory_bytes` 持续上涨 30min 告警。

---

## 9. 升级路径 (Escalation)

### L1 (一线 on-call, 0-15min)
- 接 PagerDuty / 飞书告警机器人告警
- 翻 RUNBOOK 对应章节
- 临时缓解后写 incident note (即使解决了)

### L2 (二次值班 TL, 15-60min)
- 15 分钟内 L1 无法缓解 / 影响用户 > 100
- TL 拉应急群 (飞书群: `visa-mvp-incident`)
- 评估: 限流阈值调整 / 灰度回滚 / 数据库切换

### L3 (架构组 / Mavis lead, > 60min)
- 事故超 1 小时, 或涉及数据丢失 / 安全
- 拉 Mavis 主 session 协同 (Mavis → team plan 编排多 worker 排障)
- 输出 PIR (Post-Incident Review) 文档, 24h 内

### 联系方式 (占位, 待正式化)

| 角色 | 联系方式 | 备注 |
|---|---|---|
| 一线 on-call | oncall@example.com | 24×7, 飞书/邮件双通道 |
| 二次值班 TL | tl-oncall@example.com | 工作日 9-22, 周末轮值 |
| 架构组 | arch@example.com | L3 升级 |
| 安全应急 | security@example.com | 涉及凭据泄露 / 越权 / 注入 |
| 商务 / 法务 | legal@example.com | 涉及支付合规 / 用户数据 |

> **TODO**: 上述 `example.com` 占位待替换为真实邮箱; 飞书群 ID 待 P1 事故演练后补全。

### 升级触发标准 (硬规则)
- [ ] P0 (全站不可用 / 数据丢失) → 立即 L3
- [ ] P1 (核心功能 < 50% 不可用, > 30min) → 15min 内 L2
- [ ] P2 (非核心功能受损) → 1h 内 L1 自决
- [ ] 安全相关 → 立即 L3 + security@

---

## 10. 应急检查清单 (通用)

任何 P0/P1 事故处理前, 先跑这 7 步:

- [ ] 1. 翻 RUNBOOK 对应章节
- [ ] 2. 拉应急群, 同步"我已接手, 正在排查"
- [ ] 3. `curl /health` 看当前状态快照
- [ ] 4. 备份关键状态 (DB / 日志 / 配置): `cp -r backend/data/ /tmp/incident-$(date +%Y%m%d-%H%M%S)/`
- [ ] 5. 临时缓解 (重启 / 限流 / 降级), 验证 `/health` 转 `ok`
- [ ] 6. 通知 TL + 用户 (状态页 / 公告)
- [ ] 7. 24h 内写 PIR, 更新 RUNBOOK

---

## 11. 附录: 常用命令 cheat sheet

```bash
# 健康度
curl -sS http://localhost:8000/health | jq .

# 进程 / 端口
ps aux | grep -E "uvicorn|celery|redis" | grep -v grep
lsof -i :8000
lsof -i :6379

# 日志
tail -f /Users/apple/Desktop/签证项目/backend/logs/app.log
grep -E "ERROR|Traceback" /Users/apple/Desktop/签证项目/backend/logs/app.log | tail -50

# 重启服务
pkill -f "uvicorn app.main" && sleep 2 && \
  nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 \
  > logs/uvicorn.out 2>&1 &

pkill -f "celery.*worker" && sleep 2 && \
  nohup .venv/bin/celery -A app.celery_app worker --loglevel=INFO --concurrency=4 \
  > logs/celery-worker.out 2>&1 &

# Redis
redis-cli ping
redis-cli -n 0 llen celery  # broker queue
redis-cli info memory

# DB (SQLite dev)
sqlite3 /Users/apple/Desktop/签证项目/backend/data/visa_mvp.db "PRAGMA integrity_check;"
sqlite3 /Users/apple/Desktop/签证项目/backend/data/visa_mvp.db "VACUUM;"

# 磁盘
df -h /Users/apple/Desktop/签证项目/
du -sh /Users/apple/Desktop/签证项目/backend/data/*
du -sh /Users/apple/Desktop/签证项目/backend/logs/*

# 内存 / 进程
ps aux -o pid,rss,command --sort -rss | head -20
```

---

**维护者**: Visa MVP 平台组 (Coder agent)  
**下次 review**: 2026-09-15 (季度)  
**关联文档**: `SECURITY.md` / `CONTRIBUTING.md` / `CHANGELOG.md`
