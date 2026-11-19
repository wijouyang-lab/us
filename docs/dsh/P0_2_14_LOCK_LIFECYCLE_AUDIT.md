# P0.2.14 Lock Lifecycle Audit

All early returns use finish(); release failure is LOCK_RELEASE_FAILED + cleanup_state FAILED. Lock loss after PR create records publication_state PR_CREATED. See FINAL.
