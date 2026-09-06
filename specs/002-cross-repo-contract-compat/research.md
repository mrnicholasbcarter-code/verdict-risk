# Research: 002-cross-repo-contract-compat

**Date**: 2026-09-06  
**Producer revision used for this plan**: `536c79e26e17ab3cf39e78f1844100ca9c27998e`

## Decision: Regenerate the consumer declaration from the producer CLI

- **Decision**: Replace `.verdict/compat-manifest.json` with the JSON emitted by `verdict compat manifest --json` from verdict-core at a named revision. Do not hand-edit hashes.
- **Rationale**: ADR-024 defines `verdict compat manifest` as the producer publication command and `verdict compat check --declared <path>` as the fail-closed consumer gate. Spec Q1 A forbids a policy change and a producer release; Q1 A requires verified producer evidence. The CLI is that evidence.
- **Alternatives considered**:
  - Hand-copy the RoutingDecisionContract hash only — rejected (FR-005; other contracts could drift; `manifest_hash` would be wrong).
  - Pin CI to a tag/SHA instead of `@main` — rejected (compatibility-policy change; Q1 C).
  - Change `check_compatibility()` to allow stale hashes — rejected (FR-001 fail-closed).

## Decision: Named producer revision is origin/main at plan time, re-verified at implement

- **Decision**: Plan against `536c79e`. At implement, re-read `origin/main`. If it is still `536c79e`, emit the manifest below. If it moved, emit from the new named SHA and record that SHA in the PR. CI stays `pip install git+...verdict-core.git@main`.
- **Rationale**: Spec requires a named revision, not a moving branch, for the repair receipt. CI already compares against current `main`; keeping that install line preserves fail-closed tracking of the published producer.
- **Alternatives considered**: Freeze CI to `536c79e` — rejected (would hide later producer drift).

## Decision: Live producer manifest at `536c79e`

Computed from `verdict.compatibility_manifest.build_compatibility_manifest()` at `536c79e`:

| Contract | Hash |
|----------|------|
| AvailabilitySnapshot | `sha256:9fdcdbe78f23e583001ed8f2292ce5668061f7dbc5d839f3b2536f92630e2b0e` |
| OutcomeEvent | `sha256:e993fb10752ee36e1a77fe38c85345f77f5975a93eaad78ccb0560004d64013f` |
| RoutingDecisionContract | `sha256:c1bd1b4ff2503e59c74737a85c7c6c470592f36d7b999b4c5d67a39d06f79892` |
| RuntimeCandidate | `sha256:8fc6ab26992374dc8642df68219b3a68a912a5087b61547c1be2032746f4f8cb` |
| SwarmTaskEnvelope | `sha256:d5247469d33ea404acd5b6c676329d0ef25fbbe0f2831bdf633b0a843cc90293` |
| TaskSpec | `sha256:161837be44785ac6057373eac32d1c0c2ba53b1b7e706f57e235c5e0f75c56d2` |
| WorkflowPlan | `sha256:f1f18b28116f1ec4b833c8fc580d5b1935a3ecc689a0b2f48b5ba3cbad5e00c4` |

`schema_version`: `1`  
`manifest_hash`: `sha256:7bbd4bf9b833b45116a3baa9af0f2d3e8c5fced6ca3ad2a26c315235bd93b0fa`

Current consumer declaration on this branch still has RoutingDecisionContract `sha256:d893d5c5…` and `manifest_hash` `sha256:a6088605…`. That is the mismatch CI reported (`contract_hash_mismatch` / `RoutingDecisionContract`).

verdict-node `origin/master` already matches this producer manifest in full. Core needs no code change.

## Decision: Scope is declaration + focused proof, not engine or CI policy

- **Decision**: Change `.verdict/compat-manifest.json`, add a focused test that the committed declaration matches a producer-emitted manifest, and keep `.github/workflows/ci.yml` unchanged (including the deprecated `safety check` job).
- **Rationale**: Spec FR-007/FR-008/SC-004. Product engine code is unrelated. Security-tooling failure is a later lane. CON-001 is already wired.
- **Alternatives considered**: Fold into PR #34 — rejected (Q2 A). Edit the security job to go green — rejected (FR-007).

## Decision: Rollout and rollback

- **Decision**: Producer `536c79e` is already on `main`. Consumer ships a standalone PR from this branch. Rollback is revert of that consumer PR, which restores the stale declaration and a fail-closed block — not a waived pass.
- **Rationale**: Spec FR-006 and edge case “rollback must restore fail-closed”.
- **Alternatives considered**: Merge into PR #34 then roll back mixed product+compat — rejected (Q2 A).

## Decision: Validation commands are repository-native plus the existing gate

- **Decision**: Prove the repair with `verdict compat check --declared .verdict/compat-manifest.json --json` against producer at the named revision, plus `ruff check`, `ruff format --check`, `mypy src`, and `pytest`. Do not treat a green compat check as a merge if the security job still fails.
- **Rationale**: Constitution IV and spec FR-009/SC-001/SC-004.
- **Alternatives considered**: Skip local compat check and wait for CI only — rejected (must bind to named revision locally).
