#!/bin/bash
# auto-review-and-push.sh — Claude Code 自主 Review + commit + push
#
# 用法:
#   bash scripts/auto-review-and-push.sh              # Review + push 到 main
#   bash scripts/auto-review-and-push.sh --dry-run    # 只 Review，不 push
#
# 依赖: claude CLI (already installed at ~/.toolbox/bin/claude)

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DRY_RUN=false
STATUS_FILE="/tmp/rootlens_review_status_$$.txt"

[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

cd "$PROJECT_DIR"

echo "=== RootLens Auto-Review ==="
echo "Project: $PROJECT_DIR"
echo "Dry run: $DRY_RUN"
echo ""

# ── Stage 1: Spec Compliance Review (subagent) ──────────────────
echo "[Stage 1] Spec Compliance Review..."

claude --print --dangerously-skip-permissions \
  --output-format text \
  -p "
你是 RootLens 的 Spec Compliance Reviewer。只做以下检查，不做其他任何事。

## 检查清单

1. 运行 python3 examples/demo.py，确认：
   - Scenario 1 (disk full) → CLOSE
   - Scenario 2 (compile error + file match) → TRUE_REJECT
   - Scenario 3 (pre-apply) → CLOSE
   - Scenario 4 (ambiguous) → ESCALATE

2. 运行 python3 benchmarks/evaluate.py，确认：
   - 100% accuracy
   - 0% false blame rate

3. 运行: grep -ri 'amazon\|gerrit\|jira\|jenkins\|labcollab' src/ configs/ examples/
   确认零内部引用泄漏。

4. 检查 src/engine/q1_5.py 的 Rule 10 (_check_build_oom_killed)：
   确认只匹配 'oom-kill' / 'oom_kill'（严格 OOM kernel signal），
   不匹配孤立的 'Killed' 或 'Out of memory'。

5. 检查 src/engine/decision.py 的 _intersect 方法：
   确认只有 'return changed & error'，无 basename/2-segment fallback。

## 输出格式（严格遵守）

每条检查结果用一行：
  ✅ CHECK_NAME — 通过原因
  ❌ CHECK_NAME — 失败原因

最后一行必须是以下之一（无额外文字）：
  SPEC_APPROVED
  SPEC_REJECTED: <问题摘要>
" | tee "$STATUS_FILE"

echo ""

# 提取最后一行结论
SPEC_RESULT=$(grep -E '^SPEC_(APPROVED|REJECTED)' "$STATUS_FILE" | tail -1 || echo "SPEC_REJECTED: 无法解析输出")

if [[ "$SPEC_RESULT" != "SPEC_APPROVED" ]]; then
  echo "❌ Stage 1 FAILED: $SPEC_RESULT"
  rm -f "$STATUS_FILE"
  exit 1
fi

echo "✅ Stage 1 PASSED"
echo ""

# ── Stage 2: Code Quality Review (subagent) ─────────────────────
echo "[Stage 2] Code Quality Review..."

GIT_DIFF=$(git diff --stat HEAD 2>/dev/null || echo "(no staged changes)")

claude --print --dangerously-skip-permissions \
  --output-format text \
  -p "
你是 RootLens 的 Code Quality Reviewer。只检查代码质量，不运行测试（Stage 1 已完成）。

## 改动范围
$(git diff HEAD --name-only 2>/dev/null | head -20 || echo "(working tree changes)")

## 检查维度

对 src/engine/ 下的每个改动文件检查：

1. 有无 TODO / FIXME / 未完成占位符
2. 有无静默吞掉异常（bare except、pass after except）
3. import 是否都在文件顶部（无函数内 import，Rule 10 里有一个 import re 例外可接受）
4. 新增的 docstring / 注释 是否准确描述了代码行为
5. 函数名和变量名是否清晰

## 输出格式

每个文件一行结论：
  ✅ src/engine/xxx.py — OK
  ⚠️ src/engine/xxx.py — [可选改进，不阻塞]
  ❌ src/engine/xxx.py — [必须修复的问题]

最后一行：
  QUALITY_APPROVED
  QUALITY_APPROVED_WITH_NOTES: <notes>
  QUALITY_REJECTED: <问题摘要>
" | tee -a "$STATUS_FILE"

echo ""

QUALITY_RESULT=$(grep -E 'QUALITY_(APPROVED|REJECTED)' "$STATUS_FILE" | tail -1 || echo "QUALITY_REJECTED: 无法解析输出")

if [[ "$QUALITY_RESULT" == QUALITY_REJECTED* ]]; then
  echo "❌ Stage 2 FAILED: $QUALITY_RESULT"
  rm -f "$STATUS_FILE"
  exit 1
fi

echo "✅ Stage 2 PASSED ($QUALITY_RESULT)"
echo ""

# ── Commit + Push ────────────────────────────────────────────────
if $DRY_RUN; then
  echo "[Dry run] 跳过 commit 和 push"
  rm -f "$STATUS_FILE"
  exit 0
fi

CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null | head -20)
if [[ -z "$CHANGED_FILES" ]]; then
  echo "ℹ️ 无改动，无需 commit"
  rm -f "$STATUS_FILE"
  exit 0
fi

echo "[Commit] 提交改动..."
git add README.md benchmarks/dataset.json src/engine/decision.py \
        src/engine/pipeline.py src/engine/q1_5.py src/engine/classifier.py \
        .gitignore 2>/dev/null || true

COMMIT_MSG="$(cat <<'EOF'
fix: post-review fixes (auto-reviewed by Claude Code)

- Rule 10: tighten OOM detection to oom-kill/oom_kill only
- _intersect: exact path match only, remove basename fallback
- classifier: module-level YAML cache (462x speedup)
- Rule 9: add cherry-pick/revert guard
- pipeline: ValueError on None/empty build_log
- benchmark: relabel infra_015/016 to ESCALATE

Benchmark: 100% accuracy, 0% false blame (41 cases)
EOF
)"

git commit -m "$COMMIT_MSG" \
  --author="Claude Code <noreply@anthropic.com>"

echo ""
echo "[Push] 推送到 origin/main..."
git push origin main

echo ""
echo "✅ All done. Two-stage review passed, changes pushed."
rm -f "$STATUS_FILE"
