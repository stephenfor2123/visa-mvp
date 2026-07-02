#!/bin/bash
# scripts/run_full_day.sh
#
# Htex 7×24h 持续可用性 + 业务流回归调度器
#
# 用法：
#   bash scripts/run_full_day.sh           # 单轮完整跑（约 5 分钟）
#   bash scripts/run_full_day.sh --loop    # 循环跑，每轮间隔 30 分钟（接近 24h）
#
# 输出：
#   - 控制台：每个 case 的 PASS/FAIL
#   - 文件：logs/run_full_day_<timestamp>.log 完整记录
#
# 覆盖：
#   case10  — 调度器 poll-tick e2e
#   case11  — (预留)
#   case12  — 注册-下单-支付-后端同步回归
#   case13  — 拒签退费链路 + 缺口标注
#   case14  — 环境稳定性 / 24h NFR
#   case15  — 数据完整性 / 丢数据防护

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="${ROOT_DIR}/logs"
mkdir -p "$LOG_DIR"

STAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/run_full_day_${STAMP}.log"

if [[ "${1:-}" == "--loop" ]]; then
  LOOP_MODE=1
  echo "Loop mode: every 30min until stopped"
else
  LOOP_MODE=0
fi

# 颜色输出（CI 用 plain）
if [[ -t 1 ]]; then
  C_RED=$'\033[0;31m'; C_GREEN=$'\033[0;32m'; C_YELLOW=$'\033[0;33m'; C_OFF=$'\033[0m'
else
  C_RED=""; C_GREEN=""; C_YELLOW=""; C_OFF=""
fi

run_case() {
  local case_name="$1"
  local case_script="$2"
  local shift_min="$3"  # 估计耗时(分钟)，仅用于调度展示

  # 等 10s 让 rate limit (100/min) reset（除非是 case14 first health ping）
  if [[ "$case_name" != "case14_env_stability" ]]; then
    sleep 10
  fi
  echo -e "${C_YELLOW}>>> ${case_name} (est ${shift_min}m)${C_OFF}" | tee -a "$LOG_FILE"
  local start=$(date +%s)
  if PYTHONPATH="${ROOT_DIR}/backend" "${ROOT_DIR}/backend/.venv/bin/python" "$case_script" 2>&1 | tee -a "$LOG_FILE"; then
    local rc=${PIPESTATUS[0]}
    local dur=$(( $(date +%s) - start ))
    if [[ $rc -eq 0 ]]; then
      echo -e "${C_GREEN}<<< ${case_name} PASSED (${dur}s)${C_OFF}" | tee -a "$LOG_FILE"
      return 0
    fi
  fi
  echo -e "${C_RED}<<< ${case_name} FAILED${C_OFF}" | tee -a "$LOG_FILE"
  return 1
}

run_full_round() {
  local round_start=$(date +%s)
  echo "" | tee -a "$LOG_FILE"
  echo "========================================================" | tee -a "$LOG_FILE"
  echo "Round @ $(date -Iseconds)" | tee -a "$LOG_FILE"
  echo "========================================================" | tee -a "$LOG_FILE"

  local failed=0
  local passed=0

  # case12 — 业务流回归 (W35)
  if run_case "case12_e2e_regression" "${SCRIPT_DIR}/case12_e2e_regression.py" 1; then
    passed=$((passed+1))
  else
    failed=$((failed+1))
  fi

  # case13 — 拒签退费
  if run_case "case13_reject_refund" "${SCRIPT_DIR}/case13_reject_refund.py" 1; then
    passed=$((passed+1))
  else
    failed=$((failed+1))
  fi

  # case15 — 数据完整性
  if run_case "case15_data_integrity" "${SCRIPT_DIR}/case15_data_integrity.py" 1; then
    passed=$((passed+1))
  else
    failed=$((failed+1))
  fi

  # case14 — 环境稳定性（包含 30s 长 session 测试，整轮会多花 30s+）
  if run_case "case14_env_stability" "${SCRIPT_DIR}/case14_env_stability.py" 2; then
    passed=$((passed+1))
  else
    failed=$((failed+1))
  fi

  local total=$((passed + failed))
  local dur=$(( $(date +%s) - round_start ))
  echo "" | tee -a "$LOG_FILE"
  echo "Round summary: ${passed}/${total} PASSED in ${dur}s" | tee -a "$LOG_FILE"

  return $failed
}

# main
if [[ $LOOP_MODE -eq 1 ]]; then
  ROUND=1
  while true; do
    echo "==== ROUND ${ROUND} ===="
    run_full_round
    ROUND=$((ROUND+1))
    # 30 分钟间隔（1800 秒），含 5 分钟跑 case 本身
    echo "Sleeping 30min until next round..."
    sleep 1800
  done
else
  run_full_round
fi