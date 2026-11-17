# P0.1.4: DSH Cloud Deployment Blocker Audit

Date: 2026-11-17
Base: `fix/dsh-single-agent-mode` @ `d7bad451053d8fb355cac9658bb79dd5d82efe1a`
Branch: `fix/dsh-p0-1-4-deploy-blockers`
Status: **DEPLOYMENT-READY LOCAL — MAIN PROTECTION STILL UNVERIFIED**

## 1. Main protection API

Old call:

```text
GET /repos/{owner}/{repo}/branches/main/protection
```

This may require Administration: read and returns 404 when unprotected.

New call:

```text
GET /repos/{owner}/{repo}/branches/main
```

and reads `protected`.

Fail-closed rules:

- non-zero API exit -> `false`;
- empty output -> `false`;
- output not `true` -> `false`.

No GITHUB_TOKEN permission is added.

Actual repository state at audit time:

```text
protected: false
```

so real cloud tasks remain blocked until a human enables protection.

## 2. BLOCKED recovery

New `TaskStore.resume_protection_blocked()`:

- only `status=BLOCKED` with
  `last_review.reason=MAIN_PROTECTION_UNVERIFIED`;
- otherwise returns false;
- sets `QUEUED`, appends history, preserves attempts;
- normal claim then increments attempts.

No other BLOCKED reason is auto-resumed.

Test:

1. same task is BLOCKED by protection;
2. protection now returns true;
3. task becomes QUEUED;
4. normal claim runs;
5. status reaches REVIEW_PENDING;
6. history contains `resume_protection_blocked`.

## 3. Deployment PR structure

Current nested chain:

```text
#561 feature/dsh-headless-automation
  -> #562 fix/dsh-p0-1-hardening
    -> #563 fix/dsh-p0-1-1-guardrails
      -> #564 fix/dsh-p0-1-2-review-guards
        -> #565 fix/dsh-single-agent-mode
          -> P0.1.4 branch
```

Recommended merge order:

1. #561 -> main
2. #562 -> updated #561 base
3. #563 -> updated #562 base
4. #564 -> updated #563 base
5. #565 -> updated #564 base
6. P0.1.4 -> updated #565 base
7. final deployment PR `deploy/dsh-automation` -> main

Do not merge in this task. This avoids losing any guardrail commit and puts
`dsh-task.yml` on the default branch so `workflow_dispatch` can appear.

A deployment Draft PR is opened from `deploy/dsh-automation` to `main` with all
P0-P0.1.4 files. It must remain Draft until human review.

## 4. Tests

```text
29 passed, 1 skipped locally
```

Coverage includes:

- protection true;
- protection false;
- API error fail-closed;
- BLOCKED -> QUEUED -> run;
- non-protection BLOCKED not resumed;
- workflow_dispatch and default-branch deployment text check.

## 5. Remaining

1. GitHub main protection is false.
2. `DEEPSEEK_API_KEY` is not configured.
3. No cloud DSH run.
4. No real ChatGPT PR review yet.
5. Auto-merge disabled.

## Final state

```text
P0_1_4_STATUS: DEPLOYMENT_READY_LOCAL
PROTECTION_API: BRANCH_ENDPOINT
PROTECTION_FAIL_CLOSED: YES
PROTECTION_BLOCKED_RECOVERY: TESTED
NESTED_PR_CHAIN: DOCUMENTED
DEPLOYMENT_PR_BASE: main
CLOUD_DSH_RUN: NOT_EXECUTED
AUTO_MERGE: DISABLED
MAIN_MODIFIED: NO
```
