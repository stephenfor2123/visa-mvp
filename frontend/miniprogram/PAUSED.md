# 微信小程序 — 暂停维护

> **决策日期**: 2026-07-11  
> **原因**: 优先服务**越南、印尼海外客户**（Web 端），帮其办理美签/申根/英签/澳签；微信小程序暂缓。

## 当前状态

- `frontend/miniprogram/` 代码保留，**不再迭代**
- 后端 `WECHAT_APPID` / `WECHAT_APPSECRET` 留空即可
- 用户主路径：**Web (Vue 3)** + 四语 i18n（含 id / vi）

## 恢复时

1. 申请微信小程序 AppID
2. 填 `backend/.env` 的 `WECHAT_APPID` + `WECHAT_APPSECRET`
3. 用微信开发者工具导入 `frontend/miniprogram/`
