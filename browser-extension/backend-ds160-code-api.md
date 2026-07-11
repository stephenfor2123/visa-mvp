# Htex DS-160 插件 · 后端 API 设计

> 版本: v0.2(2026-07-09) · 配套: [DESIGN-v0.2.md](./DESIGN-v0.2.md)
> 适用范围: 浏览器插件 → Htex 后端 鉴权 + 档案下发
> 路径前缀: `/api/v2/ds160`

---

## 0. TL;DR

两个端点,搞定"code 签发 + 兑换":

| 端点 | 调用方 | 鉴权 | 行为 |
|---|---|---|---|
| `POST /api/v2/ds160/code` | Htex Web | Session cookie / Bearer | 签发/复用 12 位 code |
| `POST /api/v2/ds160/code/redeem` | 浏览器插件 | **无**(code 即凭据) | 兑换档案 |

**核心安全模型**:
1. `ds160_code` 是随机 12 位 base30 (≈ 60 bits 熵)
2. `ds160_fingerprint` 是档案规范化后的 SHA-256 (不可逆)
3. 两者**独立**:光有 code 拿不到档案,光有 fingerprint 也还原不了字段
4. **redeen 时重算 fingerprint 比对** —— 用户改档案 → 老 code 立刻 409 失效
5. **限频** + **审计 log** —— 防爆破 / 留痕

---

## 1. 数据库 Schema

### 1.1 字段新增 (在 `backend/app/models/order.py`)

```python
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func

class Order(Base):
    __tablename__ = "orders"
    # ... 既有字段保持不变

    # === v0.2 新增 (DS-160 插件对接) ===
    ds160_code = Column(String(12), nullable=True, index=True)
    ds160_fingerprint = Column(String(64), nullable=True)
    ds160_code_issued_at = Column(DateTime(timezone=True), nullable=True)
    ds160_code_consumed_count = Column(Integer, default=0, nullable=False)
    ds160_last_redeemed_at = Column(DateTime(timezone=True), nullable=True)
    ds160_code_revoked = Column(Boolean, default=False, nullable=False)  # 用户主动 rotate 时
```

### 1.2 迁移脚本 (`backend/scripts/migrate_ds160_code_fields.py`)

```python
# 纯 Alembic 或 SQL (与项目既有迁移风格保持一致,这里给示例 SQL)
ALTER TABLE orders
  ADD COLUMN ds160_code VARCHAR(12) NULL,
  ADD COLUMN ds160_fingerprint VARCHAR(64) NULL,
  ADD COLUMN ds160_code_issued_at TIMESTAMP WITH TIME ZONE NULL,
  ADD COLUMN ds160_code_consumed_count INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN ds160_last_redeemed_at TIMESTAMP WITH TIME ZONE NULL,
  ADD COLUMN ds160_code_revoked BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX ix_orders_ds160_code ON orders(ds160_code);
-- 注: 已有订单 ds160_code = NULL, 首次访问 /code 端点时按需生成
```

### 1.3 审计 log (复用 `audit_log` 表)

redeem 事件写到既有 `audit_log` (43 行, 已存在):
```
event_type = 'ds160_code_redeemed'
actor_user_id = <order.user_id>
resource_type = 'order'
resource_id = <order.id>
metadata = { fingerprint, ip, ua, success: true/false, error_code }
```

---

## 2. 共享工具 (`backend/app/core/ds160.py`)

### 2.1 fingerprint 算法

```python
# backend/app/core/ds160.py
import hashlib, json
from datetime import date, datetime

# 哪些字段进入 fingerprint (顺序敏感, 顺序定下来就不再变)
_FP_FIELDS = [
    ('identity',   ['surname', 'givenName', 'nativeName', 'sex', 'maritalStatus',
                    'dob', 'birthCity', 'birthCountry', 'nationality', 'nationalId',
                    'hasOtherNationality']),
    ('passport',   ['type', 'number', 'bookNumber', 'issueCountry', 'issueCity',
                    'issueDate', 'expiry']),
    ('contact',    ['street', 'city', 'state', 'postalCode', 'country', 'phone', 'email']),
    ('travel',     ['purpose', 'hasPlan', 'arrivalDate', 'stayLength', 'usAddress',
                    'payer', 'hasCompanions',
                    'companion.surname', 'companion.givenName', 'companion.relation']),
    ('previous',   ['hasVisited', 'lastVisitDate', 'lastVisitStayDays', 'hasVisa',
                    'lastVisaNumber', 'lastVisaDate', 'hasRefused']),
    ('usContact',  ['personSurname', 'personGivenName', 'orgName', 'relation',
                    'street', 'city', 'state', 'zip', 'phone', 'email']),
    ('work',       ['occupation', 'employer', 'employerStreet', 'employerCity',
                    'employerState', 'employerPostal', 'employerCountry', 'employerPhone',
                    'monthlySalary', 'duties', 'hasEducation', 'schoolName',
                    'courseOfStudy', 'schoolFrom', 'schoolTo', 'prevEmployer']),
    ('family',     ['spouse.surname', 'spouse.givenName', 'spouse.dob', 'spouse.nationality',
                    'father.surname', 'father.givenName', 'father.dob', 'father.inUS',
                    'mother.surname', 'mother.givenName', 'mother.dob', 'mother.inUS',
                    'hasUSRelatives', 'relative.surname', 'relative.givenName',
                    'relative.relation', 'relative.status']),
]

def _normalize(v):
    if v is None: return ''
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, (date, datetime)): return v.isoformat()[:10]
    return str(v).strip().lower()

def compute_fingerprint(profile: dict) -> str:
    """基于 profile 的规范化快照算 SHA-256, 取 hex 前 32 位.
       任何字段变化 -> 整个 hash 雪崩 -> 老 code 立刻失效.
    """
    flat = {}
    for section, paths in _FP_FIELDS:
        sec = profile.get(section) or {}
        for p in paths:
            keys = p.split('.')
            v = sec
            for k in keys:
                v = (v or {}).get(k) if isinstance(v, dict) else None
            flat[f'{section}.{p}'] = _normalize(v)
    payload = json.dumps(flat, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:32]
```

### 2.2 code 生成

```python
import secrets

_ALPHABET = '23456789ABCDEFGHJKMNPQRSTVWXYZ'  # 30 字符 (无 0/O/1/I/L/U)
_CODE_LEN = 12

def generate_code() -> str:
    """12 位 base30 ≈ 60 bits 熵, 30^12 ≈ 5.3e17."""
    return ''.join(secrets.choice(_ALPHABET) for _ in range(_CODE_LEN))
```

### 2.3 profile 加载 (复用 useApplicantProfile 逻辑)

```python
# backend/app/core/ds160.py (续)
from app.models.applicant import Applicant
from app.models.order import Order
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def load_applicant_profile(db: AsyncSession, order: Order) -> dict:
    """从 order.applicants 加载,合成 frontend/web/src/composables/useApplicantProfile.js
       等价的 server-side 版本. 字段路径完全一致 (identity.* / passport.* / ...)."""
    apps = (await db.execute(
        select(Applicant).where(Applicant.order_id == order.id).order_by(Applicant.seq)
    )).scalars().all()
    if not apps:
        return {}
    a = apps[0]   # 单人先行; v0.4 多申请人时按 order.applicants 全展开
    # ... 字段映射 (与 web 端 useApplicantProfile.js 字段路径一致)
    return {
        'identity': {...},
        'passport': {...},
        # ...
    }
```

---

## 3. 限频 (Redis)

```python
# backend/app/core/ds160.py
# 限频键: ds160:redeem:<order_id>  60s / 5 次
#        ds160:redeem:ip:<ip>      60s / 10 次 (跨 order 防爆破)
async def check_redeem_rate_limit(redis, order_id: str, ip: str) -> tuple[bool, str]:
    """返回 (allowed, error_code)."""
    keys = [f'ds160:redeem:{order_id}', f'ds160:redeem:ip:{ip}']
    limits = [5, 10]
    for k, lim in zip(keys, limits):
        v = await redis.incr(k)
        if v == 1:
            await redis.expire(k, 60)
        if v > lim:
            return False, 'RATE_LIMITED'
    return True, ''
```

---

## 4. 端点 1: `POST /api/v2/ds160/code`

### 4.1 用途

Htex Web 订单详情页点 "去 DS-160 填表" 时调。**幂等**:档案不变 → 返旧 code;档案变 → 返新 code。

### 4.2 鉴权

复用现有 session 鉴权 (`Depends(get_current_user)` 或类似)。用户必须拥有该订单。

### 4.3 请求

```http
POST /api/v2/ds160/code
Host: api.htexvisa.com
Authorization: Bearer <session-token>
Content-Type: application/json

{
  "order_id": 12345,
  "force_rotate": false          // 可选, 用户主动重置时为 true
}
```

### 4.4 响应 — 成功 (200)

```json
{
  "order_id": 12345,
  "code": "K7H3-N9XR-A2BQ",         // 12 位 base30, 展示时前端可加中划线分组
  "fingerprint": "a3f1e9c2b4d8...",   // 32 位 hex
  "issued_at": "2026-07-09T13:00:00Z",
  "unchanged": false,                  // true = 复用旧 code, false = 新生成
  "expires_hint": "档案若有更新, code 会自动变化"
}
```

### 4.5 错误码

| HTTP | error_code | 触发条件 | 客户端应对 |
|---|---|---|---|
| 401 | `UNAUTHORIZED` | session 无效 | 重定向登录 |
| 403 | `NOT_ORDER_OWNER` | 用户非该订单 owner | 隐藏按钮 |
| 404 | `ORDER_NOT_FOUND` | order_id 不存在 | 跳转 404 |
| 409 | `ORDER_NOT_READY` | 订单状态不允许生成 code (e.g. 已取消) | 提示"订单状态不支持" |
| 422 | `MISSING_FIELDS` | 必填字段缺失无法生成有效 fingerprint | 提示用户先补完资料 |
| 429 | `RATE_LIMITED` | 60s 内同一用户生成 > 10 次 | UI 节流 |

### 4.6 业务逻辑伪代码

```python
@router.post("/code")
async def issue_ds160_code(
    req: IssueCodeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 1. 鉴权: 必须 order owner
    order = await db.get(Order, req.order_id)
    if not order:
        raise HTTPException(404, "ORDER_NOT_FOUND")
    if order.user_id != user.id:
        raise HTTPException(403, "NOT_ORDER_OWNER")
    if order.status not in {'paid', 'in_progress', 'submitted'}:
        raise HTTPException(409, "ORDER_NOT_READY")

    # 2. 加载档案 + 算 fingerprint
    profile = await load_applicant_profile(db, order)
    if not profile or not _has_minimum_fields(profile):
        raise HTTPException(422, "MISSING_FIELDS")
    fp_new = compute_fingerprint(profile)

    # 3. 幂等: code 还在且 fingerprint 一致 -> 返旧
    if not req.force_rotate and order.ds160_code and order.ds160_fingerprint == fp_new and not order.ds160_code_revoked:
        return {
            'order_id': order.id,
            'code': order.ds160_code,
            'fingerprint': fp_new,
            'issued_at': order.ds160_code_issued_at.isoformat(),
            'unchanged': True,
            'expires_hint': '档案若有更新, code 会自动变化',
        }

    # 4. 生成新 code (recycle 旧的; 防 race 用短锁)
    new_code = generate_code()
    while await db.scalar(select(Order).where(Order.ds160_code == new_code)):
        new_code = generate_code()  # 极小概率, 重抽

    order.ds160_code = new_code
    order.ds160_fingerprint = fp_new
    order.ds160_code_issued_at = datetime.utcnow()
    order.ds160_code_consumed_count = 0
    order.ds160_code_revoked = False
    await db.commit()

    return {
        'order_id': order.id,
        'code': new_code,
        'fingerprint': fp_new,
        'issued_at': order.ds160_code_issued_at.isoformat(),
        'unchanged': False,
        'expires_hint': '档案若有更新, code 会自动变化',
    }
```

---

## 5. 端点 2: `POST /api/v2/ds160/code/redeem`

### 5.1 用途

浏览器插件输入 12 位 code → 后端校验 → 返回档案。

**注意: 此端点无 session 鉴权。code 即凭据。** HTTPS + 限频 + audit 共同防御。

### 5.2 请求

```http
POST /api/v2/ds160/code/redeem
Host: api.htexvisa.com
Content-Type: application/json
User-Agent: Mozilla/5.0 ... (Chrome extension MV3)

{
  "code": "K7H3N9XRA2BQ"            // 12 位 (后端去中划线/空格容错)
}
```

### 5.3 响应 — 成功 (200)

```json
{
  "order_id": 12345,
  "profile": { /* ApplicantProfile, 与 web useApplicantProfile 同结构 */ },
  "fingerprint": "a3f1e9c2b4d8...",
  "mapping_version": "2026.2",
  "mapping_verified_date": null,
  "issued_at": "2026-07-09T13:00:00Z"
}
```

### 5.4 错误码

| HTTP | error_code | 触发条件 | 客户端应对 |
|---|---|---|---|
| 400 | `INVALID_CODE_FORMAT` | 不是 12 位 base30 | 输入框红边 |
| 404 | `CODE_NOT_FOUND` | code 不存在 | 输入框红边 + "code 不存在" |
| 409 | `ARCHIVE_CHANGED` | fingerprint 不匹配 (用户改了档案) | **关键路径** → 提示用户回 Htex 拿新 code |
| 409 | `CODE_REVOKED` | 用户主动 rotate 过 | 同上 |
| 422 | `PROFILE_INCOMPLETE` | 档案关键字段缺失 (理论上 /code 已拦, 兜底) | 提示用户先补完 |
| 429 | `RATE_LIMITED` | 60s/5 次 or 60s/10 次/IP | UI 倒计时重试 |

### 5.5 业务逻辑伪代码

```python
@router.post("/code/redeem")
async def redeem_ds160_code(
    req: RedeemRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    # 1. 格式校验
    code = re.sub(r'[^A-Z0-9]', '', req.code.upper())
    if not re.fullmatch(r'[2-9A-HJ-NP-Z]{12}', code):
        raise HTTPException(400, "INVALID_CODE_FORMAT")

    # 2. 限频
    ip = request.client.host
    order_id_placeholder = code[:6]   # 不知道 order_id 前用 code 前缀限频
    allowed, err = await check_redeem_rate_limit(redis, order_id_placeholder, ip)
    if not allowed:
        raise HTTPException(429, err)

    # 3. 查 order
    order = (await db.execute(
        select(Order).where(Order.ds160_code == code)
    )).scalar_one_or_none()
    if not order:
        await _audit(db, None, ip, request, success=False, error='CODE_NOT_FOUND')
        raise HTTPException(404, "CODE_NOT_FOUND")

    # 4. 撤销检查
    if order.ds160_code_revoked:
        await _audit(db, order, ip, request, success=False, error='CODE_REVOKED')
        raise HTTPException(409, "CODE_REVOKED")

    # 5. **关键**: 重算 fingerprint 比对
    profile = await load_applicant_profile(db, order)
    fp_now = compute_fingerprint(profile)
    if order.ds160_fingerprint != fp_now:
        await _audit(db, order, ip, request, success=False, error='ARCHIVE_CHANGED')
        raise HTTPException(409, "ARCHIVE_CHANGED", detail={
            'hint': '档案已更新, 请回 Htex 拿新 code',
            'issued_fingerprint': order.ds160_fingerprint[:8] + '...',
            'current_fingerprint': fp_now[:8] + '...',
        })

    # 6. 成功: 返回档案 + 更新审计字段
    order.ds160_code_consumed_count += 1
    order.ds160_last_redeemed_at = datetime.utcnow()
    await db.commit()
    await _audit(db, order, ip, request, success=True)

    return {
        'order_id': order.id,
        'profile': profile,
        'fingerprint': fp_now,
        'mapping_version': DS160_VERSION,                # 从 frontend/web/src/data/ds160FieldMap.js 同源
        'mapping_verified_date': DS160_VERIFIED_DATE,
        'issued_at': order.ds160_code_issued_at.isoformat(),
    }
```

---

## 6. 测试矩阵

### 6.1 单元测试 (`backend/tests/unit/test_ds160.py`)

```python
def test_fingerprint_changes_on_any_field():
    base = _profile_fixture()
    fp1 = compute_fingerprint(base)
    for section, paths in _FP_FIELDS:
        for p in paths:
            modified = _deep_set(base, section, p, _DIFFERENT_VALUE)
            fp2 = compute_fingerprint(modified)
            assert fp1 != fp2, f'{section}.{p} 没有让 fingerprint 变化!'
            # 雪崩: 差异不在固定位置
            assert sum(a != b for a, b in zip(fp1, fp2)) >= 16

def test_fingerprint_stable_across_whitespace_and_case():
    a = {'identity': {'surname': '  NGUYEN  ', 'givenName': 'Van A'}}
    b = {'identity': {'surname': 'nguyen',    'givenName': 'van a'}}
    assert compute_fingerprint(a) == compute_fingerprint(b)

def test_fingerprint_normalizes_dates():
    a = {'identity': {'dob': '1992-05-14'}}
    b = {'identity': {'dob': '14/05/1992'}}
    c = {'identity': {'dob': '14 MAY 1992'}}
    assert compute_fingerprint(a) == compute_fingerprint(b) == compute_fingerprint(c)

def test_fingerprint_handles_missing_sections():
    assert compute_fingerprint({}) == compute_fingerprint({'identity': None})

def test_generate_code_format():
    for _ in range(100):
        c = generate_code()
        assert len(c) == 12
        assert re.fullmatch(r'[2-9A-HJ-NP-Z]{12}', c)

def test_generate_code_uses_secrets():
    # 不应该重复 (1000 次内 collision < 0.001)
    codes = {generate_code() for _ in range(1000)}
    assert len(codes) == 1000
```

### 6.2 API 集成测试 (`backend/tests/api/test_ds160_api.py`)

```python
async def test_issue_code_idempotent_when_archive_unchanged(client, db, user_with_order):
    r1 = await client.post('/api/v2/ds160/code', json={'order_id': user_with_order.id})
    assert r1.status_code == 200
    r2 = await client.post('/api/v2/ds160/code', json={'order_id': user_with_order.id})
    assert r2.json()['code'] == r1.json()['code']
    assert r2.json()['unchanged'] is True

async def test_issue_code_regenerates_when_field_changed(client, db, order):
    r1 = await client.post('/api/v2/ds160/code', json={'order_id': order.id})
    order.applicants[0].surname = 'TRAN'  # 改姓
    await db.commit()
    r2 = await client.post('/api/v2/ds160/code', json={'order_id': order.id})
    assert r2.json()['code'] != r1.json()['code']
    assert r2.json()['unchanged'] is False

async def test_redeem_succeeds_when_fingerprint_matches(client, db, order):
    code = (await client.post('/api/v2/ds160/code', json={'order_id': order.id})).json()['code']
    r = await client.post('/api/v2/ds160/code/redeem', json={'code': code})
    assert r.status_code == 200
    assert 'profile' in r.json()
    assert 'identity' in r.json()['profile']

async def test_redeem_rejects_old_code_after_archive_change(client, db, order):
    code = (await client.post('/api/v2/ds160/code', json={'order_id': order.id})).json()['code']
    order.applicants[0].city = 'Ho Chi Minh'  # 改地址
    await db.commit()
    r = await client.post('/api/v2/ds160/code/redeem', json={'code': code})
    assert r.status_code == 409
    assert r.json()['detail']['error'] == 'ARCHIVE_CHANGED'

async def test_redeem_rejects_revoked_code(client, db, order):
    code = (await client.post('/api/v2/ds160/code', json={'order_id': order.id})).json()['code']
    await client.post('/api/v2/ds160/code', json={'order_id': order.id, 'force_rotate': True})
    r = await client.post('/api/v2/ds160/code/redeem', json={'code': code})
    assert r.status_code == 409
    assert r.json()['detail']['error'] == 'CODE_REVOKED'

async def test_redeem_rate_limited(client, db, order):
    code = (await client.post('/api/v2/ds160/code', json={'order_id': order.id})).json()['code']
    for _ in range(5):
        await client.post('/api/v2/ds160/code/redeem', json={'code': code})
    r = await client.post('/api/v2/ds160/code/redeem', json={'code': code})
    assert r.status_code == 429

async def test_redeem_rejects_invalid_format(client):
    r = await client.post('/api/v2/ds160/code/redeem', json={'code': 'too-short'})
    assert r.status_code == 400

async def test_redeem_returns_404_for_unknown_code(client):
    r = await client.post('/api/v2/ds160/code/redeem', json={'code': 'K7H3N9XRA2BQ'})  # 合法格式但不存在
    assert r.status_code == 404

async def test_issue_code_rejects_non_owner(client, db, other_user_order, current_user):
    r = await client.post('/api/v2/ds160/code', json={'order_id': other_user_order.id})
    assert r.status_code == 403
```

### 6.3 端到端 (Playwright + 真插件, 待补)

```
1. 真 Chrome 加载未打包 extension (chrome://extensions → 开发者模式 → 加载已解压)
2. 在 Htex Web 拿到 code
3. 插件 popup 粘贴 → 看到 "✅ 已就绪"
4. 打开 ceac.state.gov → 面板显示 → 自己登 → 填表 → Next
5. 回到 Htex 改一个字段 → 重新拿 code → 插件 redeem 老 code → 看到 "ARCHIVE_CHANGED" 红色提示
```

---

## 7. 错误码总表

| error_code | HTTP | 触发 | UX 提示 |
|---|---|---|---|
| `UNAUTHORIZED` | 401 | Htex Web session 无效 | 跳转登录 |
| `NOT_ORDER_OWNER` | 403 | 用户非 order owner | 隐藏按钮 / 提示无权限 |
| `ORDER_NOT_FOUND` | 404 | order_id 不存在 | 提示订单不存在 |
| `CODE_NOT_FOUND` | 404 | code 不存在或拼错 | "code 不存在, 请检查" |
| `ORDER_NOT_READY` | 409 | 订单状态不允许 | "订单状态不支持, 请联系客服" |
| `ARCHIVE_CHANGED` | 409 | fingerprint 不匹配 | "档案已更新, 请回 Htex 重新生成 code" |
| `CODE_REVOKED` | 409 | 用户主动 rotate 过 | "code 已重置, 请回 Htex 拿新 code" |
| `INVALID_CODE_FORMAT` | 400 | 12 位 base30 校验失败 | 输入框红边 |
| `MISSING_FIELDS` | 422 | 必填档案字段缺失 | "请先在 Htex 补完必填字段" |
| `PROFILE_INCOMPLETE` | 422 | redeem 时档案关键字段缺失 (兜底) | 同上 |
| `RATE_LIMITED` | 429 | 限频触发 | "操作太频繁, 请稍后再试" |

---

## 8. 监控指标 (埋点)

埋点字段建议 (写到 audit_log + 单独的 metric):

| 指标 | 类型 | 用途 |
|---|---|---|
| `ds160_code_issued_total` | counter | 按 unchanged=true/false 分维度 |
| `ds160_code_redeemed_total` | counter | 按 success / error_code 分维度 |
| `ds160_redeem_archive_changed_total` | counter | **关键信号**: 用户改档案的频率 → UX 反馈 |
| `ds160_redeem_latency_ms` | histogram | 端到端响应 |
| `ds160_fingerprint_compute_ms` | histogram | 算法性能 |
| `ds160_audit_event_total` | counter | 审计事件流 (可接 SIEM) |

---

## 9. 文件清单 (本 API 在仓库中的位置)

```
backend/
  app/
    api/v2/
      ds160.py                      # 本设计落地的 router (~150 行)
    core/
      ds160.py                      # fingerprint + code 生成 + profile 加载 (~80 行)
    models/
      order.py                      # +6 列 (见 §1.1)
  scripts/
    migrate_ds160_code_fields.py    # 数据库迁移
  tests/
    unit/test_ds160.py              # fingerprint / code 单测
    api/test_ds160_api.py           # 端点集成
```

---

## 10. 实施顺序

1. **DB 迁移** (加列 + 索引) — 5 分钟
2. **`backend/app/core/ds160.py`** (fingerprint + code + profile) — 半天
3. **`backend/app/api/v2/ds160.py`** (两个端点 + audit + 限频) — 半天
4. **单测 + 集成** — 半天
5. **手动 curl 验证** (起 dev 后端) — 半小时
6. **对接 Htex Web** (订单详情页加按钮) — 1 小时
7. **对接浏览器插件** (popup 重写 + manifest 更新) — 半天
8. **真 Chrome e2e** (装插件 + 跑通) — 1 小时

合计: **2-3 天** (含测试)