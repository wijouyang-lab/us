# P0.1.5: DSH Credential Isolation and Release Permission Audit

Date: 2026-11-17
Branch: `deploy/dsh-automation-p0`
Base HEAD: `186f4aa422845c32b02dcdb321752f8f5ee191e1`
Status: **CODE_SECURITY_TESTED — CLOUD RUN NOT EXECUTED**

## 1. Credential isolation

`actions/checkout@v4` now uses:

```yaml
persist-credentials: false
```

No GitHub token remains in the workspace `.git/config`.

`HeadlessRunner` builds a minimal child env:

- allowed runtime: `PATH`, `HOME`, `USERPROFILE`, `SYSTEMROOT`, temp/locale,
  proxy, `DSH_HOME`;
- model auth: `DEEPSEEK_API_KEY`;
- explicitly removed: `GH_TOKEN`, `GITHUB_TOKEN`, `GITHUB_ENTERPRISE_TOKEN`,
  `CODEX_CMD`.

The locked DSH `0.2.0-rc.2` subprocess runtime also scrubs credential-shaped
names and `DSH_*` variables before spawning shell tools. Tests confirm the DSH
child cannot see `GH_TOKEN`/`GITHUB_TOKEN` and can see model auth.

## 2. Outer release permissions

- DSH runs first; outer Orchestrator uses GitHub write credentials only after
  the child exits.
- push uses a per-command helper:

```text
git -c credential.helper=!gh auth git-credential push ...
```

- no token is persisted into `.git/config`;
- `gh pr create --draft` remains outer-only;
- DSH has no `gh` token, so it cannot push `main` or open/approve PRs;
- no merge path.

## 3. Protection caveat

`protected=true` alone is not a full policy. The following still require human
verification:

- block direct pushes;
- block force pushes and deletion;
- require selected CI checks;
- require human review.

Current repository state:

```text
branches/main: protected=false
```

Therefore cloud tasks remain:

```text
BLOCKED / MAIN_PROTECTION_UNVERIFIED
```

No token permission was added and repository settings were not modified.

## 4. Tests

```text
tests/test_dsh_automation.py
tests/test_dsh_hardening.py
tests/test_dsh_runtime_guardrails.py
32 passed, 1 skipped
```

Added tests:

- DSH child env excludes GitHub credentials, preserves model key;
- checkout uses `persist-credentials: false`;
- failed DSH does not publish;
- existing protected/recovery/rename/timeout/whitelist tests.

Full CI: to be recorded on the final commit.

## 5. Remaining

1. main is not protected; cloud DSH remains blocked;
2. no cloud DSH run;
3. no real ChatGPT PR review;
4. `DEEPSEEK_API_KEY` not configured in this environment;
5. no auto-merge/auto-approval;
6. full branch-protection rules (direct push/force/PR checks/review) not
   readable with current permission; human verification required.

## Final state

```text
CODE_SECURITY_TESTED
DSH_CLOUD_RUN_NOT_EXECUTED
CHATGPT_REVIEW_PENDING
AUTO_MERGE_DISABLED
MAIN_PROTECTION: FALSE
MAIN_MODIFIED_NO
```
