#!/usr/bin/env bash
# OUTBOUND PII guard: scan only data leaving the machine (Bash commands, WebFetch URLs/bodies).
# Does NOT scan ordinary file writes. Allowlists reserved test ranges. No-op without jq.
command -v jq >/dev/null 2>&1 || exit 0
input=$(cat)
payload=$(printf '%s' "$input" | jq -r '(.tool_input.command // "") + " " + (.tool_input.url // "") + " " + (.tool_input.prompt // "")')

# Strip reserved/synthetic test values so fixtures are never flagged.
scan=$(printf '%s' "$payload" \
  | sed -E 's/[A-Za-z0-9._%+-]+@(example\.(com|org|net)|test\.local)//g' \
  | sed -E 's/555-01[0-9][0-9]//g')

# SSN, credit-card-shaped 13-16 digit runs, emails, US-style phone numbers.
if printf '%s' "$scan" | grep -Eq '([0-9]{3}-[0-9]{2}-[0-9]{4})|([0-9]{13,16})|([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})|(\(?[0-9]{3}\)?[-. ][0-9]{3}[-. ][0-9]{4})'; then
  echo "Blocked: this outbound action appears to contain PII. Redact or tokenize before sending." >&2
  exit 2
fi
exit 0
