# Contact User-Agent Configuration

## Variables

Use only secure environment/GitHub Actions secrets:

- `OFFICIAL_FEED_USER_AGENT` for BLS/Fed official RSS;
- `SEC_USER_AGENT` for SEC EDGAR.

Do not put real names/emails in code, tests, issues, logs, or public reports.

## Validation

`tools/research/contact_user_agent.py`:

- non-empty, single-line, <=256 chars;
- no control characters;
- SEC requires a syntactically valid contact email;
- BLS contact-required feeds require a real contact email;
- placeholder domains (`example.com`, `example.org`, `example.net`,
  `test.com`, `localhost`) and placeholder locals (`test`, `user`, `contact`,
  `noreply`, etc.) are rejected;
- missing/invalid values never trigger a request;
- `redact_user_agent` masks the local part for diagnostics.

## Current state

No real identity is configured in the current environment. Therefore:

- BLS remains `skipped_missing_contact_user_agent`;
- SEC remains unrequested;
- no request is reported as executed.

Required configuration is user-supplied; do not send secrets in chat.
