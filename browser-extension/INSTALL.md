# Htex DS-160 浏览器插件 — 安装说明

## 语言设计（重要）

- **插件界面**（popup、面板按钮）可以是中文，方便越南/印尼用户操作。
- **写入 ceac.state.gov 的值** 必须是 **DS-160 官网英文枚举**：
  - 例如 `M` → `MALE`，`single` → `SINGLE`，`VN` → `VIETNAM`
  - App 里的中/越/印尼文案 **不会** 被直接填进官网
- 若档案值无法映射到英文下拉项，插件会标 **待补**，不会乱填。

## 安装（Chrome / Edge）

1. 解压 `htex-ds160-extension-v0.2.0.zip`（或直接使用本目录）
2. 打开 `chrome://extensions`（Edge: `edge://extensions`）
3. 开启 **开发者模式**
4. 点击 **加载已解压的扩展程序**
5. 选择 `browser-extension` 文件夹

## 使用流程

1. 在 Htex Web 订单详情页点击 **生成 DS-160 code**
2. 点击插件图标，粘贴 12 位 code → **Redeem**
3. 打开 [ceac.state.gov/genniv](https://ceac.state.gov/genniv/)
4. 登录并进入填表页 → 右上角 Htex 面板 → **填充本页**
5. 核对绿色高亮字段 → 自己点 **Next**
6. **Sign & Submit 由你本人完成**（插件不代点）。提交成功进入确认页后，插件检测到会弹绿色横幅 → 点 **「我已提交完成」** 记录状态（只记时间，不上传确认码）。之后 popup 里会显示「DS-160 已确认提交」。

## 开发 / 更新 mapping

字段映射权威源：`frontend/web/src/data/ds160FieldMap.js`

```bash
cd frontend/web
node scripts/build-extension-mapping.mjs   # 生成 browser-extension/src/mapping.js
cd ../../browser-extension
npm test
```

## API 地址

Popup 底部可改 API Base（默认 `http://localhost:8000`）。生产环境填 `https://api.htexvisa.com`。
