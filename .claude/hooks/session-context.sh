#!/usr/bin/env bash
# Printed to stdout, which is injected into the opening context. Keep it short and fast.
D="${CLAUDE_PROJECT_DIR:-.}"
echo "== Product =="
[ -f "$D/PRODUCT_BRIEF.md" ] && sed -n '1,20p' "$D/PRODUCT_BRIEF.md" || echo "(no PRODUCT_BRIEF.md yet)"
echo "== Agents =="
ls "$D/.claude/agents" 2>/dev/null | sed 's/\.md$//' | sed 's/^/- /' || echo "(none)"
echo "== Working tree =="
git -C "$D" status -s 2>/dev/null | head -20
exit 0
