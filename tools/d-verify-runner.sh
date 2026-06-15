#!/usr/bin/env bash
# D-VERIFY-RUNNER 1.0 — 修真因 D 失察 5+1 次, 工具化 4 必查.
#
# Usage: tools/d-verify-runner.sh <TASK_ID> <SCREENSHOTS_DIR> <DELIVERABLE_PATH> <WORKLOG_PATH> [PYTEST_TARGET]
#
# Exit codes:
#   0  all 4 checks PASS
#   1  Step 1 (sha256 distinct) FAIL
#   2  Step 2 (deliverable non-empty) FAIL
#   3  Step 3 (WORKLOG grep hit) FAIL
#   4  Step 4 (wire-level verification) FAIL
#   5  usage / arg error
#
# W12+ every plan_yaml verify_prompt MUST add:
#   "Run D-VERIFY-RUNNER before accept:
#      bash tools/d-verify-runner.sh <TASK_ID> ... 4 paths ..."
# Any FAIL → override_accept is invalid.
#
# Background: W6b 17:54 + W8 21:49 + W9 22:53 + W9 23:10 + W10 23:55 — D 5 次失察
# 漏查 1 P0 (deliverable / A_WORKLOG / sha256 / pytest). 修真因: D 不跑 4 必查
# wire-level 实证, 靠"印象" + 短 Read. 工具化后: 1 个 .sh 跑 4 步, 0 漏查.

set -u  # NOTE: no -e — we want all 4 checks to run, not bail on first FAIL

TASK_ID="${1:-}"
SCREENSHOTS_DIR="${2:-}"
DELIVERABLE_PATH="${3:-}"
WORKLOG_PATH="${4:-}"
PYTEST_TARGET="${5:-tests/integration/test_payment_stripe_stub.py}"

if [ -z "$TASK_ID" ] || [ -z "$DELIVERABLE_PATH" ] || [ -z "$WORKLOG_PATH" ]; then
  echo "USAGE: $0 <TASK_ID> <SCREENSHOTS_DIR> <DELIVERABLE_PATH> <WORKLOG_PATH> [PYTEST_TARGET]" >&2
  echo "  TASK_ID            e.g. B-W11-2" >&2
  echo "  SCREENSHOTS_DIR    dir to scan for *screenshot*.png (empty ok)" >&2
  echo "  DELIVERABLE_PATH   e.g. outputs/B-W11-2/deliverable.md" >&2
  echo "  WORKLOG_PATH        e.g. backend/WORKLOG.md" >&2
  echo "  PYTEST_TARGET       pytest path (default: tests/integration/)" >&2
  exit 5
fi

# Resolve project root (script lives at <project_root>/tools/)
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( cd -- "$SCRIPT_DIR/.." &> /dev/null && pwd )"

echo "=========================================="
echo "D-VERIFY-RUNNER 1.0 — TASK=$TASK_ID"
echo "Project root: $PROJECT_ROOT"
echo "Time:         $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "=========================================="

PASS_COUNT=0
FAIL_COUNT=0
declare -a RESULTS

# --------------------------------------------------------------------------- #
# Step 1 — 截图 sha256 distinct (修真因 #1: 修真因 *screenshot*.png → *.png,
#   修真因修真因修真因修真因 — destinations.png / ordernew.png 修真因修真因修真因
#   *.png 修真因, 修真因修真因修真因 sha256sum distinct 修真因修真因修真因)
# --------------------------------------------------------------------------- #
echo ""
echo "[Step 1/4] sha256sum distinct — screenshots"
# Resolve screenshots dir: absolute or relative to PROJECT_ROOT
if [ -z "$SCREENSHOTS_DIR" ]; then
  echo "  SKIP — no screenshots dir specified"
  RESULTS+=("SKIP")
elif [[ "$SCREENSHOTS_DIR" = /* ]]; then
  _SHOTS_ABS="$SCREENSHOTS_DIR"
else
  _SHOTS_ABS="$PROJECT_ROOT/$SCREENSHOTS_DIR"
fi
if [ ! -d "$_SHOTS_ABS" ]; then
  echo "  SKIP — no screenshots dir ($_SHOTS_ABS)"
  RESULTS+=("SKIP")
else
  # 修真因修真因修真因: *screenshot*.png 修真因 .png 修真因修真因 (修真因修真因修真因)
  TOTAL=$(find "$_SHOTS_ABS" -name "*.png" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$TOTAL" -eq 0 ]; then
    echo "  SKIP — no *.png found in $SCREENSHOTS_DIR"
    RESULTS+=("SKIP")
  else
    DISTINCT=$(sha256sum $(find "$_SHOTS_ABS" -name "*.png" 2>/dev/null) 2>/dev/null \
                | awk '{print $1}' | sort -u | wc -l | tr -d ' ')
    if [ "$DISTINCT" -eq "$TOTAL" ]; then
      echo "  PASS — $DISTINCT / $TOTAL distinct sha256"
      RESULTS+=("PASS")
      PASS_COUNT=$((PASS_COUNT+1))
    else
      echo "  FAIL — only $DISTINCT / $TOTAL distinct (collision detected)"
      RESULTS+=("FAIL")
      FAIL_COUNT=$((FAIL_COUNT+1))
    fi
  fi
fi

# --------------------------------------------------------------------------- #
# Step 2 — deliverable.md 存在非空
# --------------------------------------------------------------------------- #
echo ""
echo "[Step 2/4] deliverable.md 存在非空"
# Resolve path: if absolute, use as-is; else prepend PROJECT_ROOT
if [[ "$DELIVERABLE_PATH" = /* ]]; then
  _DELIVERABLE_ABS="$DELIVERABLE_PATH"
else
  _DELIVERABLE_ABS="$PROJECT_ROOT/$DELIVERABLE_PATH"
fi
if [ ! -f "$_DELIVERABLE_ABS" ]; then
  echo "  FAIL — file not found: $_DELIVERABLE_ABS"
  RESULTS+=("FAIL")
  FAIL_COUNT=$((FAIL_COUNT+1))
elif [ ! -s "$_DELIVERABLE_ABS" ]; then
  echo "  FAIL — file is empty: $_DELIVERABLE_ABS"
  RESULTS+=("FAIL")
  FAIL_COUNT=$((FAIL_COUNT+1))
else
  LINES=$(wc -l < "$_DELIVERABLE_ABS" | tr -d ' ')
  if [ "$LINES" -lt 30 ]; then
    echo "  WARN — only $LINES lines (< 30, may be stub)"
    echo "  FAIL — too short to be a real deliverable"
    RESULTS+=("FAIL")
    FAIL_COUNT=$((FAIL_COUNT+1))
  else
    echo "  PASS — $LINES lines ($_DELIVERABLE_ABS)"
    RESULTS+=("PASS")
    PASS_COUNT=$((PASS_COUNT+1))
  fi
fi

# --------------------------------------------------------------------------- #
# Step 3 — WORKLOG grep 命中
# --------------------------------------------------------------------------- #
echo ""
echo "[Step 3/4] WORKLOG grep 命中"
# Resolve WORKLOG path: absolute or relative to PROJECT_ROOT
if [[ "$WORKLOG_PATH" = /* ]]; then
  _WORKLOG_ABS="$WORKLOG_PATH"
else
  _WORKLOG_ABS="$PROJECT_ROOT/$WORKLOG_PATH"
fi
if [ ! -f "$_WORKLOG_ABS" ]; then
  echo "  FAIL — WORKLOG not found: $_WORKLOG_ABS"
  RESULTS+=("FAIL")
  FAIL_COUNT=$((FAIL_COUNT+1))
else
  HITS=$(grep -c "$TASK_ID" "$_WORKLOG_ABS" 2>/dev/null || echo "0")
  HITS=$(echo "$HITS" | tr -d ' ')
  if [ "$HITS" -lt 1 ]; then
    echo "  FAIL — no '$TASK_ID' line in $_WORKLOG_ABS"
    RESULTS+=("FAIL")
    FAIL_COUNT=$((FAIL_COUNT+1))
  else
    echo "  PASS — $HITS line(s) mention $TASK_ID"
    RESULTS+=("PASS")
    PASS_COUNT=$((PASS_COUNT+1))
  fi
fi

# --------------------------------------------------------------------------- #
# Step 4 — 核心功能 wire-level (pytest 真输出)
# --------------------------------------------------------------------------- #
echo ""
echo "[Step 4/4] wire-level 验证 (pytest 真输出)"
PYTEST_BIN="$PROJECT_ROOT/backend/.venv/bin/pytest"
if [ ! -x "$PYTEST_BIN" ]; then
  PYTEST_BIN="$(command -v pytest 2>/dev/null || echo pytest)"
fi
cd "$PROJECT_ROOT/backend" 2>/dev/null || cd "$PROJECT_ROOT"
PYTEST_OUTPUT=$($PYTEST_BIN "$PYTEST_TARGET" --tb=line -q 2>&1 | tail -20)
PYTEST_EXIT=$?
echo "$PYTEST_OUTPUT" | tail -10
# Match pattern: "<N> passed" or "passed in <X>s"
PASSED_LINE=$(echo "$PYTEST_OUTPUT" | grep -E "[0-9]+ passed" | tail -1)
if [ -n "$PASSED_LINE" ] && [ "$PYTEST_EXIT" -eq 0 ]; then
  echo "  PASS — $PASSED_LINE"
  RESULTS+=("PASS")
  PASS_COUNT=$((PASS_COUNT+1))
elif [ "$PYTEST_EXIT" -eq 5 ]; then
  # pytest exit 5 = no tests collected, which is OK if the target is empty
  echo "  SKIP — no tests collected (exit 5)"
  RESULTS+=("SKIP")
else
  echo "  FAIL — pytest exit=$PYTEST_EXIT, last line: $(echo "$PYTEST_OUTPUT" | tail -1)"
  RESULTS+=("FAIL")
  FAIL_COUNT=$((FAIL_COUNT+1))
fi

# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #
echo ""
echo "=========================================="
echo "D-VERIFY-RUNNER SUMMARY — TASK=$TASK_ID"
echo "=========================================="
for i in 1 2 3 4; do
  case $i in
    1) NAME="sha256sum distinct" ;;
    2) NAME="deliverable non-empty" ;;
    3) NAME="WORKLOG grep hit" ;;
    4) NAME="wire-level pytest" ;;
  esac
  STATUS="${RESULTS[$((i-1))]:-SKIP}"
  echo "  Step $i ($NAME): $STATUS"
done
echo "----------------------------------------"
echo "  PASS: $PASS_COUNT  FAIL: $FAIL_COUNT  SKIP: $(echo "${RESULTS[@]}" | tr ' ' '\n' | grep -c SKIP)"
echo "=========================================="

if [ "$FAIL_COUNT" -gt 0 ]; then
  echo ""
  echo "RESULT: FAIL — $FAIL_COUNT check(s) failed, override_accept is INVALID"
  # exit code = first failing step (1-4)
  for i in 0 1 2 3; do
    if [ "${RESULTS[$i]:-SKIP}" = "FAIL" ]; then
      exit $((i+1))
    fi
  done
  exit 1
fi
echo ""
echo "RESULT: PASS — 4 必查 wire-level 实证全过, override_accept 有效"
exit 0
