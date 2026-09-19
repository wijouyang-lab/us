# US Scan V16 — ClawSocket Live Route Fix

## 2026-09-19

### Root cause isolated
- `/v1/models` confirms `gpt-6-astra`, but real POST returned HTTP 400 `Request is missing a model`.
- Claude Fable fallback could answer short requests but the long HTML report returned HTTP 524.

### Changes
1. Real startup POST probe with a tiny `OK` request. The scan locks the first verified model/protocol for the whole process.
2. GPT model routing tries both the catalog ID `gpt-6-astra` and provider-qualified `openai/gpt-6-astra`.
3. Claude routing supports both `claude-*` and `anthropic/claude-*` forms.
4. Validated runtime route is reused by all scan AI calls, avoiding repeated failed route probes.
5. Claude Fable fallback remains available only when the requested GPT route returns a model-routing error.
6. When Claude is the live fallback, the long report output cap is reduced to 8,000 tokens to reduce gateway timeout/524 risk.
7. Fixed GitHub Actions environment indentation and added the runtime routing secrets consistently to scan/review/evolve.
8. scan workflow commits `scan_version.txt` as well as pending files.

### Safety behavior
- AI failure never creates a Core recommendation.
- Programmatic Observation fallback remains available.
- No historical CSV is rewritten by this change.
