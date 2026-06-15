# scripts/seed_demo_data — 演示数据填充脚本使用说明

> 路径: `backend/scripts/seed_demo_data.py`
> 用途: 把 dev 数据库(`data/visa_mvp.db`)填上一组固定的 demo 用户/订单/材料,
> 让一个干净的 checkout 在 `git clone` 后立刻可以交互(不必手动走注册流程)。

---

## TL;DR — 三行上手

```bash
cd backend
.venv/bin/python scripts/seed_demo_data.py                       # 默认 3 个 demo 用户
.venv/bin/python scripts/seed_demo_data.py --apply-admin-password  # 同时把 ADMIN_PASSWORD_SECRET 写到 .env
.venv/bin/python scripts/seed_demo_data.py --reset --user-count 5  # 清空 demo 数据后重建 5 个
```

---

## 它会创建什么

### Demo 用户(默认 3 个,可调 `--user-count`)

| 手机号                       | 密码    | 角色                              |
| ---------------------------- | ------- | --------------------------------- |
| `+86-138001380001`           | `123456` | 新注册用户,无订单                  |
| `+86-138001380002`           | `123456` | 持有 1 个 `created` 状态的订单      |
| `+86-138001380003`           | `123456` | 持有 1 个 `submitted` + 1 个 `approved` 订单 |
| `+86-13800138000{4..N}`      | `123456` | 普通用户(无订单)                   |

> 密码 `123456` 故意**违反**产品策略(`password_min_length=8` 且必须含字母+数字)。
> 这是 demo 专用账号,**严禁**部署到生产。脚本通过直接调用 `passlib.CryptContext`
> 绕开 `validate_password_strength()`,所以能写入。
> 生产环境仍由 `AuthService.register / reset-password` 强制校验。

### Admin 账号(env-based,无需 user 行)

| 字段     | 值            |
| -------- | ------------- |
| username | `admin`       |
| password | `Admin@2024`  |

> Admin 登录走 `POST /api/v2/admin/login`,校验的是环境变量 `ADMIN_PASSWORD_SECRET`
> (而不是 users 表)。脚本**不会**自动修改 `.env`,有 2 种启用方式:
>
> 1. 一次性写入:加 `--apply-admin-password`,脚本会原子替换 `.env` 里的 `ADMIN_PASSWORD_SECRET=Admin@2024`。
> 2. 手动修改:打开 `backend/.env`,把 `ADMIN_PASSWORD_SECRET=CHANGE_ME_IN_PROD` 改成 `ADMIN_PASSWORD_SECRET=Admin@2024`。

### Demo 订单(3 条,user-count ≥ 3 时才创建)

| order_no                          | 归属用户  | 状态      | visa_type | amount | 备注                               |
| --------------------------------- | --------- | --------- | --------- | ------ | ---------------------------------- |
| `DEMO-20260615-CREATED-001`       | user #2   | `created` | tourism   | $199   | `material_ids=[<id_card>]`          |
| `DEMO-20260615-SUBMITTED-002`     | user #3   | `submitted`| tourism  | $199   | `submitted_at` 已设                |
| `DEMO-20260615-APPROVED-003`      | user #3   | `approved` | student  | $399   | `submitted_at` + `reviewed_at` 已设 |

每条订单都会在 `order_status_history` 写一条初始 `system` 来源的记录,
模拟 `OrderService.create` 的副作用。

### Demo 材料(2 条)

| user  | 类型       | sha256                       | ocr_status | 关联订单 |
| ----- | ---------- | ---------------------------- | ---------- | -------- |
| #1    | `passport` | `demo-sha-passport-001`      | `pending`  | —        |
| #2    | `id_card`  | `demo-sha-id_card-002`       | `done`     | #1(CREATED) |

---

## CLI 参数

```text
--user-count N      创建 N 个 demo 用户 (1..99,默认 3)
--reset             先按 demo 标识清空所有 demo 行,再重新插入
--destination ID    演示订单使用的 visa_destinations.id (默认 1,需 enabled)
--dry-run           跑一遍但不 commit,方便预演
--apply-admin-password  把 ADMIN_PASSWORD_SECRET=Admin@2024 写入 backend/.env
-h / --help
```

---

## 幂等性 (idempotent)

脚本按以下 key 判重,**重复运行只会 skip 已存在的行**:

- 用户:`phone + phone_country`
- 订单:`order_no`(demo 订单前缀 `DEMO-`)
- 材料:`sha256 + user_id + deleted_at IS NULL`

因此:

- 普通运行:首次创建,再次运行全部 skip(`users_skipped / orders_skipped / materials_skipped > 0`)。
- `--reset`:按 demo 标识先 DELETE 再重建(也会重建刚被 reset 掉但不在 demo 列表的订单)。

---

## 使用场景

| 场景                          | 命令                                                                       |
| ----------------------------- | -------------------------------------------------------------------------- |
| 首次 clone 后立刻 demo 可用    | `.venv/bin/python scripts/seed_demo_data.py --apply-admin-password`       |
| 演示流程多账号                 | `.venv/bin/python scripts/seed_demo_data.py --reset --user-count 8`        |
| 演示订单全清空重建             | `.venv/bin/python scripts/seed_demo_data.py --reset`                       |
| CI 校验 schema 后             | `.venv/bin/python scripts/seed_demo_data.py --dry-run` (验证不报错即可)     |
| 调试某个特定国家               | `.venv/bin/python scripts/seed_demo_data.py --destination 2`               |

---

## 输出示例

```
[--reset] Dropped demo rows: {'materials': 2, 'orders': 3, 'users': 3}

=== seed summary ===
  db_path: /Users/apple/Desktop/签证项目/backend/data/visa_mvp.db
  users_created: 3
  users_skipped: 0
  orders_created: 3
  orders_skipped: 0
  materials_created: 2
  materials_skipped: 0
  reset: True
  destination_id: 1
  reset_deleted: {'materials': 2, 'orders': 3, 'users': 3}

Demo user accounts (phone / password):
  +86-138001380001  /  123456  (nickname: demo_user_138001380001)
  +86-138001380002  /  123456  (nickname: demo_user_138001380002)
  +86-138001380003  /  123456  (nickname: demo_user_138001380003)

Admin login (POST /api/v2/admin/login):
  username: admin
  password: Admin@2024
```

---

## 注意事项 / 已知限制

- **密码 `123456` 不符合产品策略**。这是 demo 账号绕开密码强度校验,严禁生产用。
- **Admin 账号不写入 users 表**。Admin 登录验证 `ADMIN_PASSWORD_SECRET` 环境变量,
  跟 `User` 模型无关。脚本创建了 nickname=`admin` 的普通用户作为 admin 面板列表展示用。
- **数据库路径**:脚本读 `app.core.config.get_settings().database_url`,
  仅支持 `sqlite+aiosqlite:///` URL(SQLite)。Postgres 部署下请勿直接运行。
- **前置条件**:`alembic upgrade head` 必须已执行(`visa_destinations` / `users` /
  `orders` / `materials` / `order_status_history` 表都存在)。
- **直接走 stdlib `sqlite3` 而非 SQLAlchemy ORM**:脚本故意绕过 ORM 链,
  因为 `app.models.webhook_event` 在 Python 3.9 + SQLAlchemy 2.0 下解析
  `Mapped[str | None]` 失败(详见 `outputs/<this>/deliverable.md` Notes)。

---

## 验证清单

```bash
# 1. 运行前
python3 -c "import sqlite3; c=sqlite3.connect('data/visa_mvp.db'); \
  print(c.execute('SELECT count(*) FROM users').fetchone())"

# 2. 跑脚本
.venv/bin/python scripts/seed_demo_data.py

# 3. 跑两次(验证 idempotent)
.venv/bin/python scripts/seed_demo_data.py
# 第二次应该看到 users_skipped=3 / orders_skipped=3 / materials_skipped=2

# 4. --reset 验证
.venv/bin/python scripts/seed_demo_data.py --reset --user-count 5

# 5. 验证落 DB
python3 -c "import sqlite3; c=sqlite3.connect('data/visa_mvp.db'); \
  print('users:', c.execute('SELECT count(*) FROM users WHERE phone LIKE \"13800138000%\"').fetchone(), \
  'orders:', c.execute('SELECT count(*) FROM orders WHERE order_no LIKE \"DEMO-%\"').fetchone(), \
  'materials:', c.execute('SELECT count(*) FROM materials WHERE sha256 LIKE \"demo-sha-%\"').fetchone())"
# 期望:users=(5,) orders=(3,) materials=(2,)
```
