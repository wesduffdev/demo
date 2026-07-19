#!/usr/bin/env bash
# Block edits/writes to secret/credential/PII-bearing files. Exit 2 cancels the tool call
# and returns the message to Claude to self-correct. No-op if jq is unavailable.
command -v jq >/dev/null 2>&1 || exit 0
input=$(cat)
f=$(printf '%s' "$input" | jq -r '.tool_input.file_path // ""')
case "$f" in
  *.env|*.env.*|*/secrets/*|*.pem|*id_rsa*|*credentials*|*.key|*.p12|*.pfx|*keystore*)
    echo "Blocked: '$f' is a protected secret/credential file. Never write secrets to disk." >&2
    exit 2 ;;
esac
exit 0
