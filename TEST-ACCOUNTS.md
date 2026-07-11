# Htex Test Accounts & Demo Guide

> 2026-07-07 更新 — 8 位密码 + 银行流水 sample + 修正登录入口描述
>
> 给 Htex 团队 / 客户 / 投资人演示用。所有密码均为 **8 位**,符合生产密码策略(`password_min_length=8` + 字母+数字)。

## 一、Web 入口

| 环境 | URL | 说明 |
|---|---|---|
| **前端 (Web)** | http://127.0.0.1:5173 | Vite dev server,带 HMR |
| **后端 API** | http://127.0.0.1:8000 | FastAPI,Swagger 在 `/docs` |
| **后端 Health** | http://127.0.0.1:8000/health | `{"status":"ok","db_ok":true,"version":"0.1.0"}` |
| **AI 拒签诊断** | http://127.0.0.1:5173/materials/diagnose | 直接进诊断页(需先登录) |
| **管理后台** | http://127.0.0.1:5173/admin/login | `admin / HtexAd@26` |

> ⚠️ **这些 URL 是本地 dev 环境**,生产环境需要替换。

---

## 二、测试账户 (User 端)

| Email(也可用 username) | 密码 | 用途 | 说明 |
|---|---|---|---|
| `demo138001380001@htex.app` (or `demo_user_138001380001`) | `Htex@2026` | 主测试账号 | 全新用户,无订单 |
| `demo138001380002@htex.app` (or `demo_user_138001380002`) | `Htex@2026` | 有 1 个待提交订单 | 演示"待提交"状态流 |
| `demo138001380003@htex.app` (or `demo_user_138001380003`) | `Htex@2026` | 有完整申请 | 演示"审核中 / 通过"状态流 |

### 登录方式(W26 起,只支持 email / username)

```bash
POST /api/v2/auth/login
{
  "account": "demo138001380001@htex.app",   # ← email 或 username 二选一
  "password": "Htex@2026"
}
```

> ⚠️ **历史手机号登录已废弃** — 早期版本(TEST-ACCOUNTS v1 / DEMO-ACCOUNT.md)用的
> `13800138000x + 123456 / demo1234` 不再可用。`POST /api/v2/auth/login` 现在只接受
> email 或 username 作为 `account` 字段。手机号不能直接登(后端 `_get_user_by_account`
> 只走 email/username 两条分支,见 `backend/app/services/auth_service.py:40-80`)。
>
> 旧文档 `DEMO-ACCOUNT.md` 已标记为 **deprecated**,请以本文档为准。

- **JWT 有效期**: 2 小时(刷新 token 7 天)

### 重置 demo 数据

```bash
cd /Users/apple/Desktop/签证项目_副本/backend
.venv/bin/python scripts/seed_demo_data.py --reset --user-count 3
# 想要 admin 密码也写进 .env,加 --apply-admin-password
.venv/bin/python scripts/seed_demo_data.py --reset --user-count 3 --apply-admin-password
```

`--reset` 会清掉旧 demo 用户(`username LIKE 'demo_user_%'`),`--apply-admin-password`
会把 `ADMIN_PASSWORD_SECRET=HtexAd@26` 写入 `backend/.env`(idempotent)。

---

## 三、管理员账户

| 用户名 | 密码 | URL | 权限 |
|---|---|---|---|
| `admin` | `HtexAd@26` | http://127.0.0.1:5173/admin/login | 查看所有用户、订单、审计日志 |

**注意 admin 密码跟用户密码区分**:

- 用户密码 `Htex@2026` — 给 3 个普通用户用
- admin 密码 `HtexAd@26` — 给 admin 后台用(避免运营/客服拿用户密码也能登 admin)

**env 同步**: admin 密码在 `backend/.env` 的 `ADMIN_PASSWORD_SECRET` 字段。
seed 脚本 `--apply-admin-password` 会自动写入并覆盖旧值。

---

## 四、可下载的测试图片

存放位置: `outputs/test-fixtures/`

| 文件 | 类型 | 用途 |
|---|---|---|
| `01_passport_usa.jpg` | 美国护照 | 测试护照识别 + 分类 |
| `02_passport_japan.jpg` | 日本护照 | 多语言 OCR 测试 |
| `03_passport_sample.jpg` | 通用护照 | 备用 |
| `04_handheld_photo.jpg` | 手持拍的护照 (透视变形) | **测试功能1: 自动扫描剪裁** |
| `05_processed_passport.jpg` | case5 剪裁后输出 | 对比原图看效果 |
| `06_id_card_cn.png` | 中国居民身份证正面 | **测试功能2: 身份证分类** |
| `07_photo_white.png` | 白底 2 寸签证照片 | **测试功能2: 签证照分类** |
| `08_ds160_form.png` | DS-160 申请表 | **测试功能2: 申请表分类 + OCR** |
| **`09_bank_statement_zh.jpg`** | **中文银行流水(扫描版)** | **测试功能3: 银行流水识别 + 分类** |
| **`10_bank_statement_en.pdf`** | **英文银行流水(PDF 版)** | **海外签证官递签用样本 / 验证 PDF 上传路径** |

### 银行流水 sample 说明(W47c+ 新增)

- `09_bank_statement_zh.jpg`:ICBC 个人账户,6 个月(2025-12-01 → 2026-05-31),
  88 笔交易,期初余额 CNY 78,432.50 → 期末 96,215.80。视觉上扫描风(浅噪点 +
  纸张米色),方便测试 `bank_statement_parser.py` 的中文 OCR + 余额链校验。
- `10_bank_statement_en.pdf`:英文 formal 版本,带 summary(inflow / outflow /
  net / avg monthly balance),给海外签证官递签做样式参考。

**生成器**: `scripts/gen_bank_statement_sample.py`(标准库 + PIL + reportlab,无
网络依赖,可重复运行)。所有数据合成(账户号、姓名、对方账户),仅用于 demo。

---

### 国家封面图 (Destinations)

存放位置: `frontend/web/public/countries/`

| 文件 | 内容 |
|---|---|
| `fr_eiffel.jpg` | 埃菲尔铁塔 (法国主封面) |
| `fr_louvre.jpg` | 卢浮宫 |
| `fr_mont_saint_michel.jpg` | 圣米歇尔山 |
| `fr_notre_dame.jpg` | 巴黎圣母院 |
| `fr_versailles.jpg` | 凡尔赛宫 |

---

## 五、推荐测试路径 (3 分钟跑通 3 个新功能)

### Step 1: 登录

1. 打开 http://127.0.0.1:5173
2. 邮箱 `demo138001380001@htex.app` / 密码 `Htex@2026` 登录
3. 或者带 `?demo=1` 参数:`http://127.0.0.1:5173/login?demo=1` 自动预填

### Step 2: 进入 /destinations 选国家

- 看法国 (FR) 卡片:Eiffel Tower 封面 + 锯齿边缘 + 触感 hover
- 点 "申请 →"

### Step 3: /materials 上传 3-4 张测试图

依次上传(每张都看功能):

| 上传文件 | 触发功能 | 预期效果 |
|---|---|---|
| `04_handheld_photo.jpg` | **功能1: 自动扫描剪裁** | 弹出 before/after 预览,点"使用剪裁版本" |
| `06_id_card_cn.png` | **功能2: 自动分类** | 系统判断"这是 **身份证** (95%)",点"✓ 接受" |
| `07_photo_white.png` | **功能2** | 系统判断"这是 **签证照片** (95%)" |
| `08_ds160_form.png` | **功能2** | 系统判断"这是 **申请表** (95%)" |
| **`09_bank_statement_zh.jpg`** | **功能3** | 系统判断"这是 **银行流水** (95%)" |
| **`10_bank_statement_en.pdf`** | **功能3 + PDF 上传** | 验证 PDF MIME + OCR 路径 |

### Step 4: /materials/diagnose AI 拒签诊断

- 选目标国 (推荐 US)
- 选签证类型 (推荐 B2 / tourism)
- 默认全选已上传材料
- 点 "开始 AI 诊断"
- 看:风险徽章 + 优化建议 + 已达标项 + **政策引用**

### Step 5: 创建订单 → OrderNew 拉链状步骤导航

- 选目的地 → 选签证类型
- 看 4 步拉链状进度条 (1 选国家 → 2 填表 → 3 付款 → 4 RPA 提交)

---

## 六、错误代码速查

| 状态码 | 含义 | 触发场景 |
|---|---|---|
| 200 | 成功 | - |
| 400 | 请求参数错误 | 缺字段、字段类型不对 |
| 401 | 未登录 | JWT 过期或没传 |
| 403 | 权限不足 | 用户访问别人的资源 |
| 404 | 资源不存在 | 查不存在的 material/order |
| **409** | 业务冲突 | **RPA 提交时国家不在 enabled 列表 / 订单状态不允许** |
| 422 | 验证失败 | Pydantic schema 校验失败 |
| 429 | 限流 | 同一 IP 1 分钟内调用 > 6 次 |
| 500 | 服务器错误 | 内部 bug,看 `/tmp/uvicorn.log` |

---

## 七、常见问题

### Q1. 登录提示"密码最少 8 位"?

所有 demo 账户密码都是 **8 位**(`Htex@2026` / `HtexAd@26`),符合策略。请检查是否输错或
复制到空格。

### Q2. 401 弹窗一直弹?

JWT 过期 (2h) 或 localStorage 里的 token 失效。重新登录即可。

### Q3. 上传图片失败?

- 后端跑了吗?`curl http://127.0.0.1:8000/health`
- Vite 端口 5173 占了吗?`lsof -i :5173`
- 浏览器 console 有错?F12 → Network 看实际请求

### Q4. RPA 提交 409?

- 多数情况: 该国家(US/FR 等)已 enabled,但前端没传 `passport_data` 或 `order_id` 类型错了
- 少数情况: 订单状态不允许(如已 submitted 的订单不能重复提交)

### Q5. AI 诊断 "政策引用" 是空的?

RAG 知识库没数据。当前只 seed 了 ID/VN 两国政策。US/FR/JP/KR 等主流国家的政策 RAG 文档需要补到 `app/services/rag/curated_content`。

### Q6. admin 登录报"账号或密码错误"?

确认两件事:
1. `backend/.env` 第 79 行 `ADMIN_PASSWORD_SECRET=HtexAd@26`(本地 dev 默认)
2. 前端是否走了 mock: `VITE_MOCK=true` 时前端硬编码 `admin/HtexAd@26`,不走后端;
   `VITE_MOCK=false` 时才打后端 `/api/v2/admin/login`

如果改了 `ADMIN_PASSWORD_SECRET`,**重启后端**才会生效。

### Q7. 用手机号登录返 2001?

W26 后 `/api/v2/auth/login` 不再接受手机号作 account — 必须用 email 或 username。
手机号目前是用户表里的旧字段,没参与登录 lookup(详见 `auth_service._get_user_by_account`)。

---

## 八、如何扩展示例数据

```bash
# 重置 demo 数据(3 个普通用户 + admin env 密码)
cd /Users/apple/Desktop/签证项目_副本/backend
.venv/bin/python scripts/seed_demo_data.py --reset --user-count 3 --apply-admin-password

# 重置 + 重建 RAG 知识库
.venv/bin/python scripts/seed_rag_sources.py

# 批量回填 OCR + 看准确率
PYTHONPATH=backend /Users/apple/Desktop/签证项目_副本/backend/.venv/bin/python \
  /Users/apple/Desktop/签证项目_副本/scripts/batch_ocr_and_bench.py --reset
```

---

## 九、紧急联系

- 跑不起来:看 `/tmp/uvicorn.log` 末尾 50 行
- 前端改完没生效:刷新浏览器 (Vite HMR 通常自动)
- 数据库锁了:`pkill -9 -f 'uvicorn app.main:app'` 然后 `cd backend && .venv/bin/python app/main.py` 重启

---

> Last updated: 2026-07-07 by Mavis (Htex demo build session)
> 上次变更:统一 8 位密码(`Htex@2026` 用户 / `HtexAd@26` admin) + 新增银行流水 sample
> (`09_bank_statement_zh.jpg` + `10_bank_statement_en.pdf`,生成器 `scripts/gen_bank_statement_sample.py`)。