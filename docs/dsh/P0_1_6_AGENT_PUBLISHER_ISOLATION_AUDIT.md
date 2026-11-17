# P0.1.6: DSH Agent/Publisher Credential Isolation and Install Verification

Date: 2026-11-17
Branch: `deploy/dsh-automation-p0`
Base HEAD: `c8fe4ecc1cb30d9b2ad603b6eb43d2d22ef3a2f0`
Status: **CODE_SECURITY_TESTED — CLOUD RUN NOT EXECUTED**

## 1. DSH install verification

Clean temporary prefix:

```bash
npm install --prefix <tmp> --ignore-scripts --no-audit --no-fund @deepseek-ai/dsh@0.2.0-rc.2
```

Result:

```text
added 538 packages
exit code 0
```

Installed package:

```text
node_modules/@deepseek-ai/dsh/lib/bin.js --version -> 0.2.0-rc.2
node_modules/@deepseek-ai/dsh-subprocess/lib/index.js -> present
```

The locked subprocess module contains:

```text
SENSITIVE_ENV_PATTERN = /KEY|PASSWORD|SECRET|TOKEN/i
scrubbedParentEnv()
```

Clean `--profile headless --help` exited 0. No real model task was run and no
real key was configured.

`DSH_INSTALL_VERIFIED: true`

## 2. Three-job workflow

### Preflight

- permissions: `contents: read`;
- `actions/checkout` with `persist-credentials: false`;
- validates task ID/branch/base;
- queries `GET /branches/main` and reads `.protected`;
- missing/false/error -> fail closed, no Agent job.

### Agent

- separate GitHub Hosted Runner;
- permissions: `contents: read` only;
- no `pull-requests` permission;
- no `GH_TOKEN`/`GITHUB_TOKEN` in the job env;
- checkout persists no credentials;
- installs pinned DSH in `.dsh-runtime`;
- runs DSH only, then local tests;
- no git push, no `gh`, no GitHub write API;
- creates `agent-artifact` with regular files and manifest;
- `.git`, logs, tokens and credentials are excluded.

### Publisher

- separate fresh Runner;
- permissions: `contents: write`, `pull-requests: write`;
- downloads only `agent-artifact`;
- revalidates every path, hash, symlink and allowed directory;
- never executes artifact contents;
- applies files, commits, pushes with per-command
  `credential.helper=!gh auth git-credential`;
- creates Draft PR;
- persists state with the same temporary helper;
- no token in `.git/config`.

## 3. Isolation tests

```text
tests/test_dsh_automation.py
tests/test_dsh_hardening.py
tests/test_dsh_runtime_guardrails.py
tests/test_dsh_publisher.py

36 passed, 2 skipped locally
```

Skipped: POSIX process-group cleanup and symlink creation on Windows; Linux CI
executes them.

Coverage includes:

- Agent job permissions only `contents: read`;
- Publisher needs Agent and has write permissions;
- DSH child env excludes `GH_TOKEN`/`GITHUB_TOKEN`, keeps model auth;
- checkout does not persist credentials;
- artifact path traversal, unauthorized paths and `.git` rejected;
- symlink artifact rejected;
- incomplete/failed artifact not published;
- failed DSH no publish;
- temporary publisher auth helper;
- no merge path.

## 4. Protection caveat

Actual:

```text
branches/main protected = false
```

Cloud DSH remains:

```text
BLOCKED / MAIN_PROTECTION_UNVERIFIED
```

Even `protected=true` would not prove:

- direct-push block;
- force-push/delete block;
- required CI checks;
- required human review.

Those remain human verification gates.

## 5. Remaining blockers

1. main is not protected;
2. no cloud DSH run;
3. no real ChatGPT PR review;
4. `DEEPSEEK_API_KEY` not configured in this environment;
5. no auto-merge or auto-approval;
6. full protection policy not readable with current permission.

## Final state

```text
DSH_INSTALL_VERIFIED
AGENT_WRITE_TOKEN_ABSENT
PUBLISHER_ISOLATED
STATE_PUSH_AUTH_VERIFIED
CODE_SECURITY_TESTED
DSH_CLOUD_RUN_NOT_EXECUTED
CHATGPT_REVIEW_PENDING
AUTO_MERGE_DISABLED
MAIN_MODIFIED_NO
```
