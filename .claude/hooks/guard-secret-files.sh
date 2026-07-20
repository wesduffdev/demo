#!/usr/bin/env bash
# Block edits/writes to secret/credential/PII-bearing files. Exit 2 cancels the tool call
# and returns the message to Claude to self-correct. No-op if jq is unavailable.
command -v jq >/dev/null 2>&1 || exit 0
input=$(cat)
f=$(printf '%s' "$input" | jq -r '.tool_input.file_path // ""')
case "$f" in
  # `.env.example` is a committed, placeholder-only template (BD-003) — allow it
  # explicitly before the block arm. `.env`, `.env.local`, etc. still fall through
  # and are blocked. Matches ONLY a file literally named `.env.example` (at the
  # repo root or in any directory), not e.g. `prod.env.example`.
  .env.example|*/.env.example) exit 0 ;;
  *.env|*.env.*|*/secrets/*|*.pem|*id_rsa*|*credentials*|*.key|*.p12|*.pfx|*keystore*)
    echo "Blocked: '$f' is a protected secret/credential file. Never write secrets to disk." >&2
    exit 2 ;;
esac
exit 0
