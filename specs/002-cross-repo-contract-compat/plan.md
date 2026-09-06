# Implementation Plan: Cross-Repository Contract Compatibility

**Branch**: `002-cross-repo-contract-compat` | **Date**: 2026-09-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-cross-repo-contract-compat/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Restore an honest fail-closed CON-001 result for verdict-risk by regenerating `.verdict/compat-manifest.json` from `verdict compat manifest --json` at a named verdict-core revision (plan-time `536c79e`). Do not change the gate, CI install line, security job, or the open README-accuracy PR. Core already publishes RoutingDecisionContract `sha256:c1bd1b4f…`; this repo still declares `sha256:d893d5c5…`.

## Technical Context

**Language/Version**: Python 3.10+ (CI 3.11 and 3.12)

**Primary Dependencies**: Existing `llm-gate-risk` / `trade_risk_engine` package; producer CLI from verdict-core (`verdict compat manifest|check`, ADR-024)

**Storage**: File `.verdict/compat-manifest.json` (schema_version 1)

**Testing**: pytest (existing suite plus one focused declaration test); ruff check/format; mypy src; `verdict compat check --json`

**Target Platform**: Linux CI (`ubuntu-latest`) and local isolated worktree

**Project Type**: Python library with CI policy gate (not a new service)

**Performance Goals**: N/A — offline hash compare, no latency budget

**Constraints**: Fail-closed CON-001; no hand-edited hashes; no CI/security-policy change; no writes to PR #34 or dirty master; one writer in this worktree

**Scale/Scope**: One consumer declaration file, one focused test, no engine changes; seven cross-repo contracts

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Coordination is not implementation | Pass | Plan binds to live producer SHA `536c79e` and ADR-024 CLI, not a handoff checkbox |
| II. Documentation before dependencies | Pass | ADR-024, `verdict/cli.py` `cmd_compat`, `compatibility_manifest.py` read before design |
| III. Repository boundaries | Pass | Risk owns the declaration; core owns contract meaning (no core code change); isolated worktree `002-cross-repo-contract-compat`; rollout/rollback named |
| IV. Verification is part of the change | Pass | Compat check + ruff + mypy + pytest required; security job failure disclosed as out of scope, not passing |
| V. Safety / least authority | Pass | No secrets; no fail-open; rollback restores fail-closed stale declaration |
| Quality gates | Pass | Repository-native checks listed; no invented numeric thresholds |

Post-Phase 1 re-check: still pass. Design adds no extra repos, no gate weakening, no undocumented interfaces.

## Project Structure

### Documentation (this feature)

```text
specs/002-cross-repo-contract-compat/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── consumer-declaration.md
└── tasks.md             # Phase 2 output (/speckit-tasks — not this command)
```

### Source Code (repository root)

```text
.verdict/
└── compat-manifest.json          # regenerated consumer declaration
.github/workflows/ci.yml          # unchanged CON-001 + security jobs
src/trade_risk_engine/            # unchanged this lane
tests/
├── test_*.py                     # existing engine tests unchanged
└── test_compat_manifest.py       # new focused declaration proof
```

**Structure Decision**: Keep the existing single Python package. The feature writes the already-present `.verdict/compat-manifest.json` and one test under `tests/`. No new packages, no workflow edits, no `src/trade_risk_engine` changes.

## Complexity Tracking

> No constitution violations. Table left empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
