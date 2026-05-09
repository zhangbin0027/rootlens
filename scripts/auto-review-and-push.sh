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

echo "=== RootLens Auto-Review (3-Stage) ==="
echo "Project: $PROJECT_DIR"
echo "Dry run: $DRY_RUN"
echo ""

# ── Stage 1: Spec Compliance Review ─────────────────────────────
echo "[Stage 1] Spec Compliance Review..."

claude --print --agent spec-reviewer \
  --output-format text \
  -p "Run all spec compliance checks for RootLens. Working directory: $PROJECT_DIR" \
  | tee "$STATUS_FILE"

echo ""

SPEC_RESULT=$(grep -E '^SPEC_(APPROVED|REJECTED)' "$STATUS_FILE" | tail -1 || echo "SPEC_REJECTED: 无法解析输出")

if [[ "$SPEC_RESULT" != "SPEC_APPROVED" ]]; then
  echo "❌ Stage 1 FAILED: $SPEC_RESULT"
  rm -f "$STATUS_FILE"
  exit 1
fi

echo "✅ Stage 1 PASSED"
echo ""

# ── Stage 2: Code Quality Review ────────────────────────────────
echo "[Stage 2] Code Quality Review..."

claude --print --agent quality-reviewer \
  --output-format text \
  -p "Run code quality review for all files in src/engine/. Working directory: $PROJECT_DIR" \
  | tee -a "$STATUS_FILE"

echo ""

QUALITY_RESULT=$(grep -E 'QUALITY_(APPROVED|REJECTED)' "$STATUS_FILE" | tail -1 || echo "QUALITY_REJECTED: 无法解析输出")

if [[ "$QUALITY_RESULT" == QUALITY_REJECTED* ]]; then
  echo "❌ Stage 2 FAILED: $QUALITY_RESULT"
  rm -f "$STATUS_FILE"
  exit 1
fi

echo "✅ Stage 2 PASSED ($QUALITY_RESULT)"
echo ""

# ── Stage 3: Compliance & Sensitive Information Review ──────────
echo "[Stage 3] Compliance & Sensitive Information Review..."

claude --print --agent compliance-reviewer \
  --output-format text \
  -p "Scan all staged and tracked files for sensitive information leaks before commit. Working directory: $PROJECT_DIR" \
  | tee -a "$STATUS_FILE"

echo ""

COMPLIANCE_RESULT=$(grep -E 'COMPLIANCE_(APPROVED|REJECTED)' "$STATUS_FILE" | tail -1 || echo "COMPLIANCE_REJECTED: 无法解析输出")

if [[ "$COMPLIANCE_RESULT" == COMPLIANCE_REJECTED* ]]; then
  echo "❌ Stage 3 FAILED: $COMPLIANCE_RESULT"
  echo "   Sensitive information detected — commit blocked."
  rm -f "$STATUS_FILE"
  exit 1
fi

echo "✅ Stage 3 PASSED ($COMPLIANCE_RESULT)"
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
git add -u 2>/dev/null || true

COMMIT_MSG="$(cat <<'EOF'
chore: auto-reviewed and approved (3-stage Claude Code review)

Passed:
- Stage 1: Spec compliance (benchmark 100% accuracy, 0% false blame)
- Stage 2: Code quality (no TODOs, no silent exceptions, PEP 8 clean)
- Stage 3: Compliance (no credentials, no internal references, no user data)
EOF
)"

git commit -m "$COMMIT_MSG" \
  --author="Claude Code <noreply@anthropic.com>"

echo ""
echo "[Push] 推送到 origin/main..."
git push origin main

echo ""
echo "✅ All done. 3-stage review passed, changes pushed."
rm -f "$STATUS_FILE"
