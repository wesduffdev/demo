#!/usr/bin/env bash
# Block irreversible / exfiltration-prone shell commands before they run. No-op without jq.
command -v jq >/dev/null 2>&1 || exit 0
input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')
case "$cmd" in
  *"rm -rf "*|*"git push --force"*|*"git push -f"*|*"git reset --hard"*|\
  *"curl "*"| sh"*|*"curl "*"| bash"*|*"wget "*"| sh"*|\
  *"chmod -R 777"*|*"DROP TABLE"*|*"DROP DATABASE"*|*"TRUNCATE "*|*"mkfs"*)
    echo "Blocked: dangerous command pattern detected. Get explicit human approval first." >&2
    exit 2 ;;
esac
exit 0
