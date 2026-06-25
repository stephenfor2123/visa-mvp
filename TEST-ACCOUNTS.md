# Htex Test Accounts & Demo Guide

> 2026-06-25 整理 — 给 Htex 团队 / 客户 / 投资人演示用

## 一、Web 入口

| 环境 | URL | 说明 |
|---|---|---|
| **前端 (Web)** | http://127.0.0.1:5173 | Vite dev server,带 HMR |
| **后端 API** | http://127.0.0.1:8000 | FastAPI,Swagger 在 `/docs` |
| **后端 Health** | http://127.0.0.1:8000/health | `{"status":"ok","db_ok":true,"version":"0.1.0"}` |
| **AI 拒签诊断** | http://127.0.0.1:5173/materials/diagnose | 直接进诊断页(需先登录) |
| **管理后台** | http://127.0.0.1:5173/admin/login | `admin / admin123` |

> ⚠️ **这些 URL 是本地 dev 环境**,生产环境需要替换。

---

## 二、测试账户 (User 端)

| 手机号 | 密码 | 用途 | 说明 |
|---|---|---|---|
| `138001380001` | `HtexDemo2026` | 主测试账号 | 全新用户,无订单 |
| `138001380002` | `HtexDemo2026` | 有 1 个待提交订单 | 演示"待提交"状态流 |
| `138001380003` | `HtexDemo2026` | 有完整申请 | 演示"审核中 / 通过"状态流 |

- **国家码**: `+86` (中国大陆)
- **登录方式**: 手机号 + 密码(已注册账户)或 手机号 + 短信码(新号码,验证码在 dev 环境固定 6 位)
- **JWT 有效期**: 2 小时(刷新 token 7 天)

---

## 三、管理员账户

| 用户名 | 密码 | URL | 权限 |
|---|---|---|---|
| `admin` | `admin123` | http://127.0.0.1:5173/admin/login | 查看所有用户、订单、审计日志 |

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
2. 手机号 `138001380001` / 密码 `HtexDemo2026` 登录

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

所有 demo 账户密码都是 `HtexDemo2026` (12 字符),请检查是否输错或复制到空格。

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

---

## 八、如何扩展示例数据

```bash
# 重置 demo 数据
cd /Users/apple/Desktop/签证项目/backend
.venv/bin/python scripts/seed_demo_data.py --reset --user-count 5

# 重置 + 重建 RAG 知识库
.venv/bin/python scripts/seed_rag_sources.py

# 批量回填 OCR + 看准确率
PYTHONPATH=backend /Users/apple/Desktop/签证项目/backend/.venv/bin/python \
  /Users/apple/Desktop/签证项目/scripts/batch_ocr_and_bench.py --reset
```

---

## 九、紧急联系

- 跑不起来:看 `/tmp/uvicorn.log` 末尾 50 行
- 前端改完没生效:刷新浏览器 (Vite HMR 通常自动)
- 数据库锁了:`pkill -9 -f 'uvicorn app.main:app'` 然后 `cd backend && .venv/bin/python app/main.py` 重启

> Last updated: 2026-06-25 by Mavis (Htex demo build session)
