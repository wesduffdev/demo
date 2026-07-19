# Rule: Destructive-Action Safety

**Severity: Critical.**

## Scope
Any agent with Bash, filesystem-write, database, or infrastructure access.

## Directives
- NEVER run irreversible or bulk-destructive commands without explicit, specific human
  approval in the same session: `rm -rf`, `git reset --hard`, `git push --force`,
  `DROP`/`TRUNCATE`/unfiltered `DELETE`/`UPDATE`, tearing down cloud resources, disabling
  backups, or overwriting production data.
- Prefer reversible operations: move-to-trash over delete, soft-delete over hard-delete, a new
  migration over a destructive schema edit, a feature branch over a direct commit to the
  default branch.
- Before any deletion, state exactly WHAT will be removed and WHY, then require confirmation.
  Never delete outside the project working directory.
- Always scope destructive SQL/CLI with a `WHERE` clause or explicit target list; refuse one
  that would affect all rows or all resources.
- NEVER operate against production from a development agent. Default data operations to a
  scoped, non-production target unless a human explicitly switches context.
- Confirm a backup or snapshot exists before any migration or schema change that could lose data.

## Enforcement
Pair with the dangerous-command guard hook (matches `rm -rf`, `git push --force`, destructive
SQL) to hard-block or force confirmation.
