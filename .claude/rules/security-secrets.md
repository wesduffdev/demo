# Rule: Security & Secrets Hygiene

**Severity: Critical.**

## Scope
Every agent that reads/writes files, runs shell commands, or calls external services.

## Directives
- NEVER hardcode secrets — API keys, tokens, passwords, private keys, connection strings — in
  source, config, comments, tests, memory, or commit history. Reference them via environment
  variables or a secrets manager.
- NEVER print, log, or echo the value of a secret. To confirm one is set, check presence only
  (e.g. `[ -n "$API_KEY" ]`), never the value.
- NEVER commit `.env`, `*.pem`, `id_rsa`, keystores, or credential files. Ensure they are in
  `.gitignore` before writing them.
- Treat all input (user, file, API) as untrusted: validate and sanitize before use. Never
  build shell commands or SQL by string-concatenating untrusted input — use parameterized
  queries and argument arrays.
- Follow least privilege: give each agent only the tools and scopes it needs.
- Do not add a new third-party dependency for a trivial need without flagging it for human
  review; pin and review what you do add.
- If you discover a leaked secret, STOP, flag it to a human, and treat it as compromised
  (assume rotation is required).

## Enforcement
Pair with the secret/credential file guard hook and a pre-commit secret scanner. Grant tools
narrowly in each subagent's `tools`/`disallowedTools`.
