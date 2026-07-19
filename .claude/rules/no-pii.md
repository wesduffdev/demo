# Rule: No PII / Data Protection

**Severity: Critical.** Once any real user data is in scope, this rule is not optional.

## Scope
Applies to every agent, tool call, log line, commit, test fixture, prompt, and memory write.

## Directives
- NEVER read, store, log, print, embed in code, or transmit personally identifiable
  information (PII): full names tied to accounts, email addresses, phone numbers, physical
  addresses, government IDs (SSN, passport, driver's license), dates of birth, precise
  geolocation, biometric data, full financial-account or card numbers, health data, or
  authentication credentials belonging to real people.
- NEVER copy production data containing PII into fixtures, seed files, test databases,
  screenshots, memory, or issue/PR descriptions. Use synthetic, clearly-fake values from
  reserved test ranges (e.g. `jane.doe@example.com`, `555-0100`, `Acme Test User`).
- When a schema or API must reference a person, store an opaque identifier (UUID,
  `account_id`) in application logic and keep PII in a dedicated, access-controlled store —
  never in application logs, analytics events, or agent memory.
- NEVER include PII in prompts sent to external models or third-party services. Redact or
  tokenize before the call.
- Mask on display by default: at most last-4 (card), domain-only (email), never full SSN —
  unless a human has explicitly approved fuller display for a specific, logged reason.
- If a task appears to REQUIRE handling real PII, STOP and escalate to the human owner before
  proceeding. Do not improvise a workaround.

## Enforcement
Guidance alone does not block anything. If PII must be hard-blocked, pair this rule with the
outbound PII hook (`guard-no-pii.sh`), which scans OUTBOUND actions (Bash/WebFetch) — not
ordinary internal file writes — so it protects against exfiltration without blocking a
legitimate contact-data feature.
