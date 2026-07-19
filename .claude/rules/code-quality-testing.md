# Rule: Code Quality & Testing Gates

**Severity: Medium.**

## Scope
Any agent that writes or modifies code.

## Directives
- Do not mark a coding task complete until it builds, the linter/formatter passes, and the
  relevant tests pass. Run them — do not assume.
- Add/update tests for every behavior change and bug fix. A bug fix MUST include a test that
  fails before the fix and passes after.
- NEVER weaken a test to make it pass, delete/skip a failing test to go green, or hardcode
  expected outputs. Fix the code; if a test is genuinely wrong, explain why before changing it.
- Keep changes scoped and reviewable: small diffs, clear names, no unrelated refactors, no
  commented-out code or debug prints.
- Match existing project conventions instead of introducing new patterns unprompted.
- Never commit directly to the default branch — use a feature branch and open a PR.

## Enforcement
Pair with the auto-format and/or test-on-change hooks, and a CI gate on PRs.
