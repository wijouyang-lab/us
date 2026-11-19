# P0.2.13 Publisher Integration Audit

`publisher_core.publish` accepts LockPort; fake lock integration tests pass. Production `publisher.main` remains OIDC then BLOCKED:LOCK_NOT_IMPLEMENTED. Legacy `_publish_main` is not yet adapter-wired: PARTIAL.
