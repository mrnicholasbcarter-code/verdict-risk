# Data Model: 002-cross-repo-contract-compat

## Entities

### Producer contract

- **Owner**: verdict-core
- **Identity**: schema hash over contract name, `contract_version`, and sorted field names/types (`verdict.compatibility_manifest._contract_schema_hash`)
- **Cross-repo set** (`CROSS_REPO_CONTRACTS`): TaskSpec, RoutingDecisionContract, AvailabilitySnapshot, RuntimeCandidate, WorkflowPlan, OutcomeEvent, SwarmTaskEnvelope
- **This lane**: do not change producer contracts. Compare against a named producer revision.

### Consumer declaration

Stored at `.verdict/compat-manifest.json`.

| Field | Type | Rules |
|-------|------|--------|
| `schema_version` | string | MUST be `"1"` (`COMPATIBILITY_MANIFEST_SCHEMA_VERSION`) |
| `contracts` | object of name → `sha256:<hex>` | MUST include every producer cross-repo contract name |
| `manifest_hash` | `sha256:<hex>` | MUST equal the producer combined hash of sorted contract entries |

Validation:

- Missing file, invalid JSON, or missing `contracts` object → fail closed
- Missing or mismatched hash for any current producer contract → `allowed=false`, `reason=contract_hash_mismatch`, `mismatched_contracts` names the failures
- Extra unknown keys in `contracts` are ignored (forward-compatible)

### Compatibility verdict

| Field | Meaning |
|-------|---------|
| `allowed` | true only when every current producer contract matches the declaration |
| `reason` | null on pass; machine reason on fail |
| `mismatched_contracts` | named mismatches; empty on pass |

### Named producer revision

- Exact git SHA of verdict-core used to emit and check the declaration
- Plan-time SHA: `536c79e26e17ab3cf39e78f1844100ca9c27998e`
- Implement-time SHA: re-read `origin/main`; if different, that SHA becomes the named revision

## State transitions

```text
stale declaration
    --[emit manifest from named producer + write file]--> regenerated declaration
regenerated declaration
    --[compat check against same producer]--> allowed | blocked(named mismatches)
allowed
    --[revert consumer PR]--> stale declaration (fail-closed block restored)
blocked
    --[do not waive]--> remains blocked until a verified emit
```

No engine, provider, or kill-switch state is part of this feature.
