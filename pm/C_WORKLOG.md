# C (Quality Gate) WORKLOG

## 2026-06-13

`W11R-CONT-b-3 | backend pytest tests/integration | passed=163 failed=1 errors=4 xfailed=1 dur=117.86s exit=2 | FAIL` (attempt 4 cap-kill retry, --maxfail=5 -q tee 落盘, 117.86s vs attempt 1 全量 406.62s; DoD 2/4 PASS 项 1/3 不通过: 1 FAIL test_w6b 5→9 页硬编码过期 + 4 ERROR test_w10 缺 results fixture, 均为非 production bug; task 明令不修测试代码, deliverable 报告 + 副跑 155 passed exit=0 证据齐)

<media src="/Users/stephen/.mavis/plans/plan_7a7ff0ff/outputs/C-W11R-S3-pytest-int/deliverable.md" />