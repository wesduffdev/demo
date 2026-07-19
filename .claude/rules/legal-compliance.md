# Rule: Legal, Licensing & Privacy Compliance

**Severity: High.**

## Scope
Applies when the product ships to users, incorporates third-party code/content, or handles
personal data of users in regulated jurisdictions.

## Directives
- Respect software licenses. Before adding a dependency or copying code, confirm the license
  permits the intended use. NEVER copy GPL/AGPL/copyleft code into a proprietary codebase, and
  NEVER strip copyright or license headers.
- Attribute and comply with the terms of any third-party content, data, model, or API you
  incorporate. Do not scrape or reuse data whose terms forbid it.
- For personal data, honor privacy-law obligations: data minimization (collect only what's
  needed), stated purpose, and support for access/deletion requests. Do not build features that
  retain personal data with no deletion path.
- NEVER generate content that facilitates unlawful activity. Do not present output as legal,
  medical, or financial advice without a human-reviewed disclaimer.
- Record data-retention, consent, and licensing assumptions in code/docs for human review.
- When a compliance question is ambiguous, escalate to a human rather than guessing. Agents
  flag issues; they do not self-certify compliance.

## Enforcement
Human/legal review gates launch decisions. Agents surface concerns and document assumptions but
must not mark a compliance question resolved on their own authority.
