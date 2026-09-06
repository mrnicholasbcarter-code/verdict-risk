# Repair path: 002-cross-repo-contract-compat

## Chosen path

Regenerate the consumer declaration from verified current producer contracts.

## Rejected paths

- Canonical producer contract release: not required; producer `main` already publishes the current RoutingDecisionContract identity.
- Compatibility-policy change: forbidden. The CON-001 gate stays fail-closed. CI still installs `verdict-core@main`.

## Owners

- Contract meaning: verdict-core
- Consumer declaration: verdict-risk (this repository)

## Named producer revision

`536c79e26e17ab3cf39e78f1844100ca9c27998e` (live `origin/main` at implement)

## Rollout

1. Producer already on `main` at the named revision.
2. This consumer branch ships a standalone PR. Do not edit PR #34.
3. Validation: `verdict compat check --declared .verdict/compat-manifest.json --json` allowed against the named producer.

## Rollback

Revert this consumer PR. The previous stale declaration must fail closed again. Do not add a skip or waiver.

## Out of scope

The CI `security` job (`safety check` / setuptools CVE) remains a separate Spec Kit lane. A green CON-001 result is not a merge.
