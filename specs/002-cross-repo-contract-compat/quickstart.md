# Quickstart: 002-cross-repo-contract-compat

Work only in this worktree. Do not edit PR #34 or dirty `verdict-risk` master.

## Prerequisites

- Isolated worktree on `002-cross-repo-contract-compat`
- Python 3.10+
- Network access to install verdict-core from GitHub at a named SHA

## 1. Name the producer revision

```bash
git ls-remote git@github.com:mrnicholasbcarter-code/verdict-core.git refs/heads/main
```

Plan-time SHA was `536c79e26e17ab3cf39e78f1844100ca9c27998e`. Use the live SHA if it differs; record it.

## 2. Emit the declaration from that producer

```bash
python -m pip install "git+https://github.com/mrnicholasbcarter-code/verdict-core.git@<NAMED_SHA>"
verdict compat manifest --json > .verdict/compat-manifest.json
```

Do not edit hashes by hand.

## 3. Check fail-closed against the same producer

```bash
verdict compat check --declared .verdict/compat-manifest.json --json
```

Expected: `"allowed": true`.  
If `mismatched_contracts` is non-empty, stop; do not waive.

## 4. Repository-native checks

```bash
ruff check src tests
ruff format --check src tests
mypy src
pytest tests -q
```

## 5. Confirm out-of-scope remains failed

The CI `security` job (`safety check` / setuptools CVE) is **not** this feature. A green compat check is not a merge.

## Rollback

Revert the consumer PR. The previous stale declaration must fail closed again; do not add a skip.
