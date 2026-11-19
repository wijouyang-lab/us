# P0.1.1: DSH Automation Final Runtime and Guardrail Audit

Date: 2026-11-17
Base: `fix/dsh-p0-1-hardening` @ `52bbf550a95a620c273c794a87866b8103886eab`
Branch: `fix/dsh-p0-1-1-guardrails`
Status: **HARDENED_LOCAL — REAL CLOUD RUN BLOCKED**

## 1. Diff and new files

New `tools/automation/changes.py`:

- `git status --porcelain=v1 -z` discovers modified, deleted and untracked files;
- only `docs/research`, `data/research`, `tools/research`, `tests` are allowed;
- unauthorized paths raise `UNAUTHORIZED_PATH` and produce `BLOCKED`;
- `git add -A -- <paths>` stages all allowed changes, including new files;
- reviewer receives `git diff --cached --binary`;
- after commit, `git diff HEAD^ HEAD --binary` must equal the staged diff.

Tests:

- new file only;
- new + modified mixed;
- unauthorized root file;
- staged diff equals committed diff.

## 2. Headless process tree

On POSIX, DSH starts in a new process group (`start_new_session=True`). On
timeout:

```text
os.killpg(os.getpgid(proc.pid), SIGKILL)
```

A real POSIX test starts a parent that starts a sleeping child; after a 0.5s
timeout, both are gone (`kill -0` fails). Windows fallback uses `proc.kill()`.
The POSIX test is skipped on Windows.

## 3. Branch safety

Checks occur:

1. before DSH execution (`_prepare_branch`);
2. immediately after headless returns;
3. before commit;
4. after commit, before push.

Any current branch equal to `main`/`master` or different from the declared task
branch raises `BRANCH_GUARD` and returns `BLOCKED`.

`base_branch` is explicit and validated. P0.1.1 PR base is
`fix/dsh-p0-1-hardening`.

## 4. Main protection

Actual API check:

```text
GET /repos/wijouyang-lab/us/branches/main/protection
HTTP 404: Branch not protected
```

Therefore:

```text
MAIN_PROTECTION: NOT_PROTECTED
REAL_CLOUD_TASK: BLOCKED
```

The automation does not modify repository settings. A non-dry-run task returns
`BLOCKED / MAIN_PROTECTION_UNVERIFIED` unless a human configures protection and
the token can confirm it.

## 5. Reviewer and PR

- Reviewer receives exactly the staged diff.
- `gh pr create` non-zero -> `FAIL / PR_CREATE_FAILED`.
- No review/PASS on PR failure.
- Missing `CODEX_CMD` -> `BLOCKED / REVIEWER_UNAVAILABLE`.
- Self-review -> `NEEDS_REVISION / SELF_REVIEW_FORBIDDEN`.
- No `gh pr merge`.

Actual Codex availability remains:

```text
interface: implemented
mock tests: pass
local real Codex CLI: not available
cloud real Codex review: not executed
```

## 6. Tests

```text
tests/test_dsh_automation.py
tests/test_dsh_hardening.py
tests/test_dsh_runtime_guardrails.py
18 passed, 1 skipped
```

Skipped test is the POSIX process-group test on Windows; Linux CI runs it.

## 7. Remaining blockers

1. `main` branch protection is not enabled; real cloud execution is blocked.
2. `DEEPSEEK_API_KEY` is not configured in this environment.
3. `CODEX_CMD` has no real Codex reviewer.
4. No cloud DSH or cloud Codex run has occurred.
5. No auto-merge or auto-approval is enabled.

## Final state

```text
P0_1_1_STATUS: HARDENED_LOCAL
STAGED_DIFF_CONSISTENCY: TESTED
UNTRACKED_NEW_FILES: INCLUDED
UNAUTHORIZED_PATHS: BLOCKED
PROCESS_GROUP_TIMEOUT: TESTED (POSIX)
BRANCH_GUARDS: TESTED
MAIN_PROTECTION: NOT_PROTECTED
REAL_CLOUD_TASK: BLOCKED
REVIEWER_UNAVAILABLE: BLOCKED
AUTO_MERGE: DISABLED
MAIN_MODIFIED: NO
```
