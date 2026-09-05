# Tasks: README Accuracy and Feature Reconciliation

**Input**: Design documents from `specs/001-readme-accuracy-and-feature-reconciliation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Organization**: Tasks grouped by user story. US1 and US2 are unconditional (P1) and
can be merged without owner decisions. US3/US4/US5 are gated on owner decisions Q1/Q2/Q3
respectively and are labelled CONDITIONAL.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to
- **[COND:Q?]**: Task is conditional on owner decision Q1, Q2, or Q3

---

## Phase 1: Setup (No new setup required)

**Purpose**: The package already has its structure. No scaffolding needed.

- [ ] T001 Audit README.md to confirm all broken links and fabricated claims; record exact line numbers in a local scratch note (no file write)
- [ ] T002 Run `uv run pytest tests/ -q` to confirm baseline passes before any change

---

## Phase 2: Foundational (Blocking Prerequisite)

**Purpose**: Read the live README against the research findings to produce a complete
edit list before touching anything.

**⚠️ CRITICAL**: T003 must complete before any README edits.

- [ ] T003 Cross-reference README.md sections (feature table, YAML config block, performance table, math properties table, links) against research.md evidence; produce an internal edit list

---

## Phase 3: User Story 1 — Accurate Repository Links (Priority: P1) MVP

**Goal**: Every link in README.md that previously pointed to `github.com/verdict/*` now
resolves correctly or is removed.

**Independent Test**:
```bash
grep -n "github.com/verdict/" README.md && echo FAIL || echo OK
curl -sI https://github.com/mrnicholasbcarter-code/verdict-core | head -1  # expect 200
curl -sI https://github.com/mrnicholasbcarter-code/verdict-backtest | head -1  # expect 200
```

- [ ] T004 [US1] Replace `github.com/verdict/verdict-core` with `github.com/mrnicholasbcarter-code/verdict-core` in README.md
- [ ] T005 [US1] Replace `github.com/verdict/verdict-backtest` with `github.com/mrnicholasbcarter-code/verdict-backtest` in README.md
- [ ] T006 [US1] Remove or replace the `github.com/verdict/verdict-edge` link in README.md (no matching repo exists; replace with roadmap note if context permits, else remove)
- [ ] T007 [US1] Verify all three `verdict/*` patterns are eliminated with `grep -n "github.com/verdict/" README.md` returning no output

**Checkpoint**: US1 independently verifiable — no broken org links remain.

---

## Phase 4: User Story 2 — Feature Table Reflects Reality (Priority: P1)

**Goal**: Every row in the README feature table, YAML config block, performance
benchmark table, and mathematical properties table matches code that exists in
`src/trade_risk_engine/`.

**Independent Test**:
```bash
# Confirm no fabricated gate names remain in feature table without a matching symbol:
python -c "import trade_risk_engine; print(dir(trade_risk_engine))"
# Confirm YAML config block is labelled operational or illustrative
grep -A2 "risk_config.yaml" README.md
```

- [ ] T008 [US2] [COND:Q2] Remove "Kelly" from the feature table row in README.md if Q2≠A; if Q2=A and US4 is complete, update the row to describe the ported function instead
- [ ] T009 [US2] [COND:Q1] Remove "correlation" from the feature table row's Kelly/correlation listing if Q1≠A; if Q1=A and US3 is complete, update the row to describe cluster cap instead
- [ ] T010 [US2] [COND:Q2] Remove the Kelly sizing performance row from the benchmark table (`Kelly sizing: 15 µs / 40 µs / 65,000 ops/s`) — fabricated; only re-add if Q2=A and a real benchmark is written
- [ ] T011 [US2] [COND:Q1] Remove the Correlation gate performance row from the benchmark table — fabricated; only re-add if Q1=A and a real benchmark is written
- [ ] T012 [US2] [COND:Q2] Remove `Kelly optimality: f* = (bp - q)/b matches analytic solution` from the mathematical properties table if Q2≠A; retain if Q2=A and T028 tests cover it
- [ ] T013 [US2] [COND:Q1] Remove `Correlation gate symmetry: corr(A,B) == corr(B,A)` from the mathematical properties table if Q1≠A; update to cluster-cap property if Q1=A and T020 tests cover it
- [ ] T014 [US2] Add a clear label to the YAML config block in README.md identifying it as "illustrative — parameters are code-injected" — SKIP this task if Q3=A; T038 handles the label for that path
- [ ] T015 [US2] Run `uv run pytest tests/ -q` and confirm all existing tests still pass after README edits

**Checkpoint**: US2 independently verifiable — README feature claims match source.

---

## Phase 5: User Story 3 — Correlation / Cluster Cap Gate [CONDITIONAL: Q1=A]

**Goal**: Port the cluster/expiry exposure cap from kalshi-trader into verdict-risk as
`evaluate_cluster_cap` in `src/trade_risk_engine/gates.py`.

**SKIP this phase if Q1 ≠ A.**

**Independent Test**: `uv run pytest tests/test_cluster_cap.py -v` — all pass.

- [ ] T016 [US3] [COND:Q1] Add `ClusterCapContext` frozen dataclass to `src/trade_risk_engine/gates.py` per `contracts/correlation.md`
- [ ] T017 [US3] [COND:Q1] Implement `evaluate_cluster_cap(ctx: ClusterCapContext) -> RiskDecision` in `src/trade_risk_engine/gates.py` — reject when `cluster_open_usd + proposed_cost > max_cluster_usd`
- [ ] T018 [US3] [COND:Q1] Handle edge case: `cluster_id == "unknown"` → always APPROVED in `src/trade_risk_engine/gates.py`
- [ ] T019 [US3] [COND:Q1] Wire `evaluate_cluster_cap` into `RiskAuthority.evaluate_trade` in `src/trade_risk_engine/engine.py` (only when `ClusterCapContext` is provided — optional kwarg)
- [ ] T020 [P] [US3] [COND:Q1] Write `tests/test_cluster_cap.py`: cover APPROVED (under cap), REJECTED (over cap), unknown cluster_id, proposed_cost=0, max_cluster_usd=0
- [ ] T021 [US3] [COND:Q1] Update README.md feature table entry for "Correlation Gate" to describe the cluster cap mechanism accurately (not a pairwise matrix)
- [ ] T022 [US3] [COND:Q1] Update README.md YAML config block to include `max_cluster_usd` and remove `max_correlation` / `lookback_window` (those are fabricated)
- [ ] T023 [US3] [COND:Q1] Run `uv run ruff check src/ tests/` and `uv run mypy src/` — fix any lint/type errors
- [ ] T024 [US3] [COND:Q1] Run `uv run pytest tests/ -q` — all tests pass including new cluster cap tests

**Checkpoint**: US3 independently verifiable — cluster cap gate present and tested.

---

## Phase 6: User Story 4 — Kelly Sizing [CONDITIONAL: Q2=A]

**Goal**: Port `_per_trade_kelly_fraction` from `~/kalshi-trader/v40/portfolio/kelly.py`
into a new `src/trade_risk_engine/kelly.py` module.

**SKIP this phase if Q2 ≠ A.**

**Independent Test**: `uv run pytest tests/test_kelly.py -v` — all pass.

- [ ] T025 [US4] [COND:Q2] Create `src/trade_risk_engine/kelly.py` with `kelly_fraction(p_win, price, conservative_fraction=0.25) -> float` per `contracts/kelly.md`
- [ ] T026 [US4] [COND:Q2] Implement NaN/inf guard in `kelly_fraction`: return 0.0 for non-finite inputs (no raise)
- [ ] T027 [US4] [COND:Q2] Implement zero-edge guard: return 0.0 when `p_win * b - (1-p_win) <= 0` in `src/trade_risk_engine/kelly.py`
- [ ] T028 [P] [US4] [COND:Q2] Write `tests/test_kelly.py`: cover positive-edge with analytic check, zero-edge (p_win == price), negative-edge, NaN/inf inputs, conservative_fraction=1.0 (full Kelly)
- [ ] T029 [US4] [COND:Q2] Export `kelly_fraction` from `src/trade_risk_engine/__init__.py`
- [ ] T030 [US4] [COND:Q2] Update README.md feature table entry for "Kelly Sizing" to match the actual formula and note `conservative_fraction=0.25` default
- [ ] T031 [US4] [COND:Q2] Run `uv run ruff check src/ tests/` and `uv run mypy src/` — fix any lint/type errors
- [ ] T032 [US4] [COND:Q2] Run `uv run pytest tests/ -q` — all tests pass including new Kelly tests

**Checkpoint**: US4 independently verifiable — Kelly sizing callable and tested.

---

## Phase 7: User Story 5 — YAML Config Loader [CONDITIONAL: Q3=A]

**Goal**: Implement `load_risk_config(path=None) -> dict` in a new
`src/trade_risk_engine/config.py` module that reads `~/.verdict/risk_config.yaml`.

**SKIP this phase if Q3 ≠ A.**

**Independent Test**: `uv run pytest tests/test_yaml_loader.py -v` — all pass.

- [ ] T033 [US5] [COND:Q3] Add `pyyaml>=6.0` to `[project.dependencies]` in `pyproject.toml`; run `uv lock` to regenerate lockfile
- [ ] T034 [US5] [COND:Q3] Create `src/trade_risk_engine/config.py` with `load_risk_config(path: Path | None = None) -> dict` per `contracts/yaml-loader.md`
- [ ] T035 [US5] [COND:Q3] Implement field validation in `load_risk_config`: TypeError on wrong type, ValueError on out-of-range value, both with field name and path in message
- [ ] T036 [P] [US5] [COND:Q3] Write `tests/test_yaml_loader.py`: cover valid config (values match), missing file (FileNotFoundError with path), invalid YAML (YAMLError), wrong type field (TypeError), out-of-range value (ValueError), unknown top-level key (warn, no raise)
- [ ] T037 [US5] [COND:Q3] Export `load_risk_config` from `src/trade_risk_engine/__init__.py`
- [ ] T038 [US5] [COND:Q3] Update README.md YAML config block label to "operational — loaded from `~/.verdict/risk_config.yaml` via `load_risk_config()`"
- [ ] T039 [US5] [COND:Q3] Run `uv run ruff check src/ tests/` and `uv run mypy src/` — fix any lint/type errors
- [ ] T040 [US5] [COND:Q3] Run `uv run pytest tests/ -q` — all tests pass including new YAML loader tests

**Checkpoint**: US5 independently verifiable — YAML loader callable, errors are explicit.

---

## Phase 8: Polish and Cross-Cutting Concerns

- [ ] T041 [P] Run `quickstart.md` steps 1 and 2 (link verification + feature table audit) to confirm unconditional scope is complete
- [ ] T042 [P] Run full `uv run pytest tests/ -v` final regression check
- [ ] T043 [P] Run `uv run verdict-risk-benchmark` — confirm no latency regression vs. main branch
- [ ] T044 Add `## Changelog` entry to README.md summarising what changed (link fixes + feature disposition) — one sentence per item
- [ ] T045 Update checklist `specs/001-readme-accuracy-and-feature-reconciliation/checklists/requirements.md` — mark all completed items [x]

---

## Dependencies and Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Start immediately — baseline audit only
- **Phase 2 (Foundational)**: Depends on Phase 1; blocks Phase 3+
- **Phase 3 (US1)**: Depends on Phase 2; unconditional; may overlap with Phase 4
- **Phase 4 (US2)**: Depends on Phase 2; unconditional; may overlap with Phase 3
- **Phase 5 (US3)**: Depends on Phase 2; gated on Q1=A
- **Phase 6 (US4)**: Depends on Phase 2; gated on Q2=A; independent of Phase 5
- **Phase 7 (US5)**: Depends on Phase 2; gated on Q3=A; independent of Phase 5/6
- **Phase 8 (Polish)**: Depends on all chosen phases

### User Story Independence

- US1 and US2 can proceed in parallel after T003
- US3, US4, US5 are each independent of each other and of US1/US2

---

## Parallel Execution Example (US1 + US2 in parallel)

```text
After T003 completes:
  Stream A (US1): T004 → T005 → T006 → T007
  Stream B (US2): T008 → T009 → T010 → T011 → T012 → T013 → T014 → T015
```

---

## Implementation Strategy

### MVP: Link fixes only (US1, no Q decision needed)

1. T001 → T002 → T003 → T004 → T005 → T006 → T007
2. Validate with grep + curl
3. Merge immediately — zero risk, zero owner decision needed

### Full P1 Delivery (US1 + US2, still unconditional)

After MVP: add T008–T015 in parallel with US1 stream.

### After Owner Decisions

- Q1=A → execute Phase 5 (T016–T024)
- Q2=A → execute Phase 6 (T025–T032)
- Q3=A → execute Phase 7 (T033–T040)
- Any combination of C → skip corresponding phase, no tasks needed

---

## Notes

- [P] tasks touch different files and have no incomplete dependencies
- Each gated phase (US3/US4/US5) is independently testable
- Do NOT implement a gated feature before the owner answers the corresponding Q
- README edits in T008–T014 must be consistent with whichever conditional phases ship

---

## Issue mirror

| Task(s) | Phase | Story | GitHub Issue | URL |
|---------|-------|-------|-------------|-----|
| T001 | 1 Setup | Unconditional | #21 | https://github.com/mrnicholasbcarter-code/verdict-risk/issues/21 |
| T002 | 1 Setup | Unconditional | #22 | https://github.com/mrnicholasbcarter-code/verdict-risk/issues/22 |
| T003 | 2 Foundational | Unconditional | #23 | https://github.com/mrnicholasbcarter-code/verdict-risk/issues/23 |
| T004 | 3 US1 | US1 | #24 | https://github.com/mrnicholasbcarter-code/verdict-risk/issues/24 |
| T005 | 3 US1 | US1 | #25 | https://github.com/mrnicholasbcarter-code/verdict-risk/issues/25 |
| T006 | 3 US1 | US1 | #26 | https://github.com/mrnicholasbcarter-code/verdict-risk/issues/26 |
| T007 | 3 US1 | US1 | #27 | https://github.com/mrnicholasbcarter-code/verdict-risk/issues/27 |
| T008–T014 | 4 US2 | US2 | #28 | https://github.com/mrnicholasbcarter-code/verdict-risk/issues/28 |
| T015 | 4 US2 | US2 | #29 | https://github.com/mrnicholasbcarter-code/verdict-risk/issues/29 |
| T016–T024 | 5 US3 | US3 [COND:Q1=A] | #30 | https://github.com/mrnicholasbcarter-code/verdict-risk/issues/30 |
| T025–T032 | 6 US4 | US4 [COND:Q2=A] | #31 | https://github.com/mrnicholasbcarter-code/verdict-risk/issues/31 |
| T033–T040 | 7 US5 | US5 [COND:Q3=A] | #32 | https://github.com/mrnicholasbcarter-code/verdict-risk/issues/32 |
| T041–T045 | 8 Polish | All | #33 | https://github.com/mrnicholasbcarter-code/verdict-risk/issues/33 |
