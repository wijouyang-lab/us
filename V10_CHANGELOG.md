# US v10 Change Log

## AI architecture
- GPT-6 Astra is the primary model for Scan, Review and Evolve.
- Claude Opus 5 is the independent Evolve red-team auditor.
- Added `ai_router.py` with native OpenAI Responses API support for GPT and native Anthropic support for Claude.
- Backward compatibility: if `GPT_API_KEY` / `OPENAI_API_KEY` is absent, GPT falls back to `CLAWSOCKET_*`.

## News sources
- Added Reuters via Google News site-targeted RSS.
- Added Federal Reserve official press-release RSS feeds.
- Added BLS official RSS feeds for macro releases.
- Kept CNBC, Yahoo Finance and Google News as supplemental sources.
- News prompt now enforces source hierarchy and conflict handling.

## Evolve safety
- GPT proposes rules.
- Claude reviews proposed rules independently.
- Only Claude-approved rule IDs are written into the active rule set.
- `core_min_score` auto-update requires time-ordered OOS validation AND Claude approval.
- OOS auto-update now requires minimum sample size, non-negative EV, and meaningful improvement over the current baseline. Negative-EV historical results cannot move the threshold automatically.
- `evolve.yml` no longer hides failures with `|| true`.

## Runtime consistency
- Scan keeps program-controlled Core/Observation and pending synchronization.
- Option engine enforces IV/Delta consistency and uses real DTE; invalid IV cannot produce a numeric Delta.
- GitHub Actions upgraded to checkout@v4 / setup-python@v5 and write permissions.
