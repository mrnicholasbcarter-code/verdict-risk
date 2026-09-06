# Contract: Consumer compatibility declaration

**Producer owner**: verdict-core (`verdict.compatibility_manifest`, ADR-024)  
**Consumer owner**: verdict-risk (this repository's `.verdict/compat-manifest.json`)  
**Gate**: fail-closed. A mismatch or missing declaration blocks. No skip, pin, or fail-open.

## Publication (producer)

```text
verdict compat manifest --json
```

Stdout is the declaration object: `schema_version`, `contracts`, `manifest_hash`.  
The consumer MUST write that stdout (or an equivalent `build_compatibility_manifest().to_dict()` serialization with `indent=2` and sorted keys) to `.verdict/compat-manifest.json`. Hashes MUST NOT be typed by hand.

Install the producer from the named revision before emitting, for example:

```text
pip install "git+https://github.com/mrnicholasbcarter-code/verdict-core.git@536c79e26e17ab3cf39e78f1844100ca9c27998e"
```

If `origin/main` has moved, substitute that SHA and record it.

## Check (consumer / CI)

Already wired in `.github/workflows/ci.yml` (do not change in this lane):

```text
pip install "git+https://github.com/mrnicholasbcarter-code/verdict-core.git@main"
verdict compat check --declared .verdict/compat-manifest.json --json
```

Pass stdout:

```json
{
  "allowed": true,
  "reason": null
}
```

Current fail stdout (stale RoutingDecisionContract):

```json
{
  "allowed": false,
  "reason": "contract_hash_mismatch",
  "mismatched_contracts": ["RoutingDecisionContract"]
}
```

Exit code 1 on any failure.

## Plan-time expected declaration at producer `536c79e`

See [research.md](../research.md) for the full object. RoutingDecisionContract MUST be `sha256:c1bd1b4ff2503e59c74737a85c7c6c470592f36d7b999b4c5d67a39d06f79892`. Combined `manifest_hash` MUST be `sha256:7bbd4bf9b833b45116a3baa9af0f2d3e8c5fced6ca3ad2a26c315235bd93b0fa`.
