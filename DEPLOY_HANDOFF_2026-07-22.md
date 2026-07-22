# Htex 前端上线交接单（2026-07-22）

## 目标

将本轮已经确认的三个前端模块上线：

1. 动态定价展示模块
2. 材料收集向导的进度、步骤与上传状态交互
3. 单次签证申请权益对比表

本轮工作此前仅在本地完成，没有提交、推送或部署。

## 应纳入上线的真实源码

### 动态定价

- `frontend/web/src/components/PricingSection.vue`

说明：保留 `usePlatformPricing` 的后台价格数据来源；修改的是展示、国家选择、费用对比和交互动效，没有把预览中的价格写死为支付价格。

### 材料收集向导

- `frontend/web/src/views/MaterialWizard.vue`
- `frontend/web/src/components/UploadItemCard.vue`
- `frontend/shared/i18n/zh-CN.json`
- `frontend/shared/i18n/en.json`
- `frontend/shared/i18n/id.json`
- `frontend/shared/i18n/vi.json`

已实现：

- 动态总进度和完成百分比
- 分类步骤的完成数量
- 当前步骤标题和完成状态
- 上传按钮图标
- 上传完成后的灰色 `Uploaded` 状态
- “清除本机数据”放在“隐私优先”区域
- `prefers-reduced-motion` 兼容

### 单次签证权益对比

- `frontend/web/src/components/PaymentBenefitsCompare.vue`
- `frontend/web/src/views/PaymentCheckout.vue`
- `frontend/shared/i18n/zh-CN.json`
- `frontend/shared/i18n/en.json`

最终产品口径：

- 这是按单次签证申请购买，不是月费或年费订阅。
- 会员列标题旁显示后台实际价格，例如 `$19.90 / 单次签证申请`。
- 不显示 `$99.90` 原价、`限时促销`和底部“平台服务费／价格快照”文案。
- 权益包含签证照片生成、尺寸剪裁和背景替换。
- 已删除“重新生成模板／再次诊断”。
- “辅助填写”和“辅助提交”已并入付费权益，不再单独显示“浏览器办理（会员专享）”分组标题。

## 仅供查看，不要作为生产入口部署

以下是独立静态预览文件，不参与 Vue 应用运行：

- `pricing-current-live-preview.html`
- `materials-motion-full-preview.html`
- `materials-three-parts-preview.html`
- `materials-integrated-current-preview.html`
- `membership-benefits-current-preview.html`

这些文件可以保留在本地，也可以不提交到 Git。不要用它们替换真实 Vue 页面。

## 特别注意：工作区有其他未提交修改

当前工作区不是干净状态，并且存在本轮以外的源码、ZIP、PNG、HTML 和工具脚本。不要直接执行 `git add .`，也不要把整个工作区无差别提交。

建议先逐个审查上述真实源码的 diff，再只暂存确认过的文件。四个 i18n JSON 文件可能还包含此前其他功能的未提交文案，不能仅凭文件名整体认定全部属于本轮；提交前应查看具体 diff。

## 上线前验证

本 session 已完成：

- `zh-CN.json`、`en.json` JSON 解析通过
- `cd frontend/web && npx vite build` 通过
- 共转换 2328 个模块
- 仅有既有的动态／静态导入提示和 chunk 大小提示，没有构建错误

交接 session 应再次执行：

```bash
cd frontend/web
npx vite build
npm test -- --run
```

如要运行项目定义的完整生产构建（包含 SEO 预渲染和审计），执行：

```bash
cd frontend/web
npm run build
```

## 人工验收清单

1. 中文和英文页面均不出现缺失的 i18n key。
2. 定价展示价格与后台定价接口返回一致。
3. 支付按钮金额、会员列金额和订单金额一致。
4. 权益表明确显示“单次签证申请”，没有订阅暗示。
5. 材料上传前显示上传图标，上传完成后显示灰色 Uploaded 状态。
6. 完成材料后，总进度、当前步骤数量和完成标签同步更新。
7. 清除本机数据可正常清除浏览器本地材料状态。
8. 桌面 Web 宽屏布局正常；本轮设计目标不是手机端重做。
9. 发布后检查支付页、材料页和首页定价区域，没有控制台异常。

## Git 与发布建议

当前分支：`main`

远端：`origin https://github.com/stephenfor2123/visa-mvp.git`

建议其他 session：

1. 先拉取远端最新状态并检查是否有冲突。
2. 新建 `codex/` 前缀发布分支。
3. 只暂存审查通过的本轮源码，不暂存静态预览、截图、ZIP 和无关文件。
4. 构建和测试通过后提交、推送。
5. 按项目既有部署流程发布，不改变后台定价或支付配置。
6. 上线后做一次真实页面冒烟测试，再确认生产订单金额。

## 可直接发送给另一个 session 的指令

> 请阅读项目根目录 `DEPLOY_HANDOFF_2026-07-22.md`，根据交接单审查本轮真实源码 diff。当前工作区有大量其他未提交改动，禁止直接 `git add .`。只选择性暂存交接单列出的、确认属于动态定价、材料向导和单次签证权益表的修改；四个 i18n 文件必须逐段审查。先运行前端构建和测试，确认支付金额、会员列金额均来自后台价格且标注为单次签证申请，然后创建 `codex/` 分支、提交、推送并按项目现有流程部署。静态 preview HTML、PNG、ZIP 和其他无关文件不要上线。发布后检查首页定价、材料向导、支付权益表和订单金额。
