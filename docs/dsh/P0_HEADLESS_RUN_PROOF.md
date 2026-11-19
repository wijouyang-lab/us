# P0 DSH Headless Run Proof

Date: 2026-11-17
Host: local Windows workspace
DSH: `0.2.0-rc.2`

Command (task text is benign; no secrets in output):

```bash
dsh --profile headless --json "Reply with exactly HEADLESS_READY"
```

Observed NDJSON events:

```json
{"type":"session","sessionId":"session-0229ccc2-acbc-4099-a7ea-17e826cdc008"}
{"type":"status","phase":"turn_start","turn":1}
{"type":"status","phase":"step_start","turn":1,"step":1}
{"type":"thinking","text":""}
{"type":"text","text":"HEADLESS_READY"}
{"type":"status","phase":"step_end","turn":1,"step":1,"usage":{"inputTokens":6110,"outputTokens":6,"cacheReadTokens":0,"cacheWriteTokens":0,"totalTokens":6116}}
{"type":"status","phase":"turn_end","turn":1,"reason":{"kind":"completed"}}
{"type":"final","text":"HEADLESS_READY"}
```

Result: **actual headless execution succeeded**.

This proof covers the CLI/auth path only. It does not prove a GitHub-hosted run;
the GitHub workflow requires `DEEPSEEK_API_KEY` and `CODEX_CMD` to be configured.


## P0.1.5 update

The production runner now passes a minimal child environment:

- no `GH_TOKEN`, `GITHUB_TOKEN`, `GITHUB_ENTERPRISE_TOKEN` or `CODEX_CMD`;
- only model/runtime facts (`DEEPSEEK_API_KEY`, `DSH_HOME`, PATH/HOME/locale);
- DSH subprocess tools additionally scrub credential-shaped names;
- checkout uses `persist-credentials: false`;
- GitHub push is performed only by the outer Orchestrator after DSH exits,
  using a temporary per-command credential helper.
