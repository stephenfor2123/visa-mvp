# Htex — DS-160 辅助填充插件(草稿 v0.1)

浏览器扩展:把用户在 Htex App 填好的资料，**辅助**填入 DS-160 官网。
半自动——插件填字段、高亮，**用户自己核对 + 点 Next/Submit**。数据只在本地。

> ⚠️ 独立草稿:**未接进 web 构建、未提交**。字段映射为**初稿，未对真表核对**。

## 目录

```
browser-extension/
  manifest.json          # MV3
  src/
    mapping.js           # DS-160 字段映射 + 引导单生成(与 App 端同源，见下)
    fillEngine.js        # 核心:锚字段标签的 DOM 填充引擎(已 jsdom 验证)
    content-ds160.js     # 注入 ceac.state.gov:悬浮面板 + 填充编排
    content-app.js       # 注入 htexvisa.com:接收 App 导出的档案
    background.js        # service worker:chrome.storage.session 暂存
  popup.html / popup.js  # 状态 + 文件导入兜底 + 清除
```

## 怎么装 / 试

1. Chrome → 扩展 → 打开"开发者模式" → "加载已解压的扩展" → 选 `browser-extension/`
2. 拿到资料的两种方式:
   - **App 直传**:在 htexvisa.com 上，App 页面 `postMessage({source:'htex-app', type:'HTEX_DS160_EXPORT', profile}, origin)`
   - **文件兜底**:App 导出档案 JSON → 点插件图标 → 导入文件
3. 打开 DS-160 官网 `ceac.state.gov/genniv/` → 右上角出现面板 → 点"填充本页" → **核对无误后自己点 Next**

**不想连官网、只想验证引擎**:真 Chrome 直接打开 `test/mock-ds160.html`(file://)→ 点"用示例档案填充" → 看它把仿真表单(含三连下拉日期)填好 + 逐项报告。

## 已验证 / 已知限制(诚实说明)

**已用 jsdom 对真实文件验证**:label 锚定定位、text/select/radio 填值、日期转
`DD-MMM-YYYY`、可选栏自动勾 Does Not Apply、找不到的框老实标 not_found(不乱填)。
select 精确优先(不会把 MALE 误配 FEMALE)。

**寻路指引(领路狗)**:
- `src/journey.js`(旅程配置:DS-160→交费/预约→面签，预约站按国家 VN/ID/CN，URL 待核实) +
  `src/wayfinder.js`(定位+高亮) + `src/content-journey.js`(检测步骤→底部提示条+把藏很深的
  "Start an Application"圈出来+箭头)。已 jsdom 验证:在干扰链接里精准定位、避开诱饵、高亮成功。
- 注入 `ceac.state.gov` 与预约站(`*.ustraveldocs.com` / `*.usvisa-info.com`)。**只指路、不替用户点政府按钮。**

**已补(本轮)**:
- ✅ **日期三连下拉(date-split)**:Date of Birth / Expiration 等按内容识别 Day(select)/
  Month(select)/Year(文本框)分别填，已 jsdom 集成测试通过(日 14 / 月 MAY / 年 1992)。
- ✅ **档案转换器**:`frontend/web/src/composables/useApplicantProfile.js` 把 wizard/OCR/表单
  收敛成 ApplicantProfile，含日期归一(MRZ `14 MAY 1992` → ISO)。引擎直接吃它的产出。
- ✅ **手动测试页**:`test/mock-ds160.html` —— 真 Chrome 直接打开(file://)点按钮即可看引擎
  填一个含三连下拉的仿真表单，不依赖官网。

**还没做 / 要注意**:
- ❌ **字段映射未对真表核对**:`VERIFIED_DATE=null`。必须对着官网逐条核 label / 下拉文案。
- ⚠️ **postback 联动(部分完成)**:`fillEngine.autoFill` 用 MutationObserver 监听——选了下拉
  后**同页新冒出的字段**会自动补填(已 jsdom 验证)。**整页刷新式的跨页**靠 content script
  在每页重新注入处理。剩余:跨页"累计进度"展示。
- ❌ **跨设备扫码(手机→电脑)**:P2。二维码传密钥 + E2E 加密临时中转，当前只有同机直传 + 文件兜底。
- ❌ **多申请人**:当前填 `applicants[0]` 语义(直接吃单个 profile)。

## 映射同步(重要)

`src/mapping.js` 与 `frontend/web/src/data/ds160FieldMap.js` 是**同一套映射**，
现在是手动复制，有漂移风险。**下一步应加构建步骤**：以 web 端那份为唯一源，
构建时自动拷贝/转换成插件版，避免两处不一致。
