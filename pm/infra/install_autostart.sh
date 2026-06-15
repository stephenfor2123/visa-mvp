#!/usr/bin/env bash
# pm/infra/install_autostart.sh
# 一键装/卸 launchd 开机自启 ngrok
# 用法:
#   bash pm/infra/install_autostart.sh           # 安装
#   bash pm/infra/install_autostart.sh --uninstall  # 卸载

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_SRC="$SCRIPT_DIR/com.ngrok.visa-mvp.plist"
PLIST_NAME="com.ngrok.visa-mvp.plist"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"

if [ "${1:-}" = "--uninstall" ]; then
  echo "卸载 $PLIST_NAME ..."
  if [ -f "$PLIST_DST" ]; then
    launchctl unload "$PLIST_DST" 2>/dev/null || true
    rm -f "$PLIST_DST"
    echo "已卸载"
  else
    echo "未安装"
  fi
  exit 0
fi

# ---------- 安装 ----------
if [ ! -f "$PLIST_SRC" ]; then
  echo "找不到 $PLIST_SRC"
  exit 1
fi

# 检查 ngrok 是否安装
if ! command -v ngrok >/dev/null 2>&1; then
  echo "⚠️  ngrok 未安装, 装上:"
  echo "    brew install ngrok   # 推荐"
  echo "    或 https://ngrok.com/download"
  echo ""
  read -p "继续装 launchd 吗?(y/N) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

# 检查 NGROK_TOKEN
if [ -z "${NGROK_TOKEN:-}" ] && [ ! -f "$HOME/.config/ngrok/ngrok.yml" ]; then
  echo "⚠️  找不到 NGROK_TOKEN, 装上(任选其一):"
  echo "  1. ngrok config add-authtoken <TOKEN>"
  echo "  2. export NGROK_TOKEN=<TOKEN> 然后跑本脚本"
  echo ""
  read -p "继续装 launchd 吗?(y/N) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

mkdir -p "$HOME/Library/LaunchAgents"
cp "$PLIST_SRC" "$PLIST_DST"
chmod 644 "$PLIST_DST"

# 如果已有同 label, 先 unload
launchctl unload "$PLIST_DST" 2>/dev/null || true

# 装并启动
launchctl load -w "$PLIST_DST"
echo "✅ 已装 $PLIST_DST"
echo ""
echo "验证: launchctl list | grep visa-mvp"
echo "日志: tail -f $SCRIPT_DIR/.ngrok.launchd.out.log"
echo "卸载: bash $0 --uninstall"
