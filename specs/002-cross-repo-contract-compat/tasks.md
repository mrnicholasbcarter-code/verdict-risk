---
description: "Task list for 002-cross-repo-contract-compat"
---

# Tasks: Cross-Repository Contract Compatibility

**Input**: Design documents from `/specs/002-cross-repo-contract-compat/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Plan requested a focused declaration test. Write it first and confirm it fails on the stale `.verdict/compat-manifest.json` before emitting a new declaration.

**Organization**: Tasks are grouped by user story. One writer in this worktree only. Do not edit PR #34, dirty `verdict-risk` master, `.github/workflows/ci.yml`, or `src/trade_risk_engine/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Single project: `.verdict/`, `tests/`, `specs/002-cross-repo-contract-compat/` at repository root of this worktree

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm isolation and name the producer revision before any declaration rewrite

- [X] T001 Re-read live `origin/main` SHA for `mrnicholasbcarter-code/verdict-core` and write it to `specs/002-cross-repo-contract-compat/producer-revision.txt` (plan-time lead was `536c79e26e17ab3cf39e78f1844100ca9c27998e`; replace if `origin/main` moved)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Install the named producer so emit/check use the same revision

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 Create gitignored `.venv` in this worktree and install verdict-core at the SHA in `specs/002-cross-repo-contract-compat/producer-revision.txt` (do not commit `.venv`)
- [X] T003 Run `verdict compat manifest --json` from that install and save stdout to `specs/002-cross-repo-contract-compat/producer-manifest.json` without editing hashes by hand

**Checkpoint**: Named producer SHA and producer-emitted manifest exist. User stories can start.

---

## Phase 3: User Story 1 - Honest compatibility verdict (Priority: P1) 🎯 MVP

**Goal**: The committed consumer declaration matches the named producer, and the fail-closed check allows it without a waiver.

**Independent Test**: `verdict compat check --declared .verdict/compat-manifest.json --json` prints `"allowed": true` against the named producer. A stale declaration still fails closed with `RoutingDecisionContract` named.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T004 [US1] Add failing tests in `tests/test_compat_manifest.py` that `.verdict/compat-manifest.json` has `schema_version` `1`, includes every key from `specs/002-cross-repo-contract-compat/producer-manifest.json`, and does not keep RoutingDecisionContract `sha256:d893d5c55f520733bc6b117efa050a188f7450fb045aa386370687c429d8edfc`; also copy the current stale file to `tests/fixtures/stale-compat-manifest.json` and assert `verdict compat check --declared tests/fixtures/stale-compat-manifest.json --json` is not allowed and names `RoutingDecisionContract`

### Implementation for User Story 1

- [X] T005 [US1] Replace `.verdict/compat-manifest.json` with the exact contents of `specs/002-cross-repo-contract-compat/producer-manifest.json` (copy, do not retype hashes)
- [X] T006 [US1] Run `verdict compat check --declared .verdict/compat-manifest.json --json` against the named producer and write `specs/002-cross-repo-contract-compat/compat-check-receipt.json` containing at least `allowed` (must be true), `producer_revision` from `producer-revision.txt`, and `consumer_head` from `git rev-parse HEAD`; do not skip or waive. If `producer-revision.txt` is not the live producer `origin/main` SHA, re-run T001–T005 against that live SHA before recording the receipt.
- [X] T007 [US1] Re-run `pytest tests/test_compat_manifest.py` and confirm T004 now passes on `.verdict/compat-manifest.json` while `tests/fixtures/stale-compat-manifest.json` still fails closed with `RoutingDecisionContract` named

**Checkpoint**: Compat check is honestly allowed; focused tests pass. Security job is still out of scope.

---

## Phase 4: User Story 2 - Evidence-backed repair path (Priority: P1)

**Goal**: Reviewers can read the recorded path, owners, and rollout without inferring them from the JSON file.

**Independent Test**: `specs/002-cross-repo-contract-compat/repair-path.md` names regenerate-declaration, rejects producer-release and policy-change, names core as contract owner and risk as declaration owner, and states rollback is revert of this consumer PR.

### Implementation for User Story 2

- [X] T008 [US2] Write `specs/002-cross-repo-contract-compat/repair-path.md` with: chosen path (regenerate consumer declaration), rejected paths, owners, named producer SHA from `producer-revision.txt`, rollout (producer already on main; consumer PR next), rollback (revert restores fail-closed stale declaration)

**Checkpoint**: Repair path is recorded independently of the JSON rewrite.

---

## Phase 5: User Story 3 - Keep unrelated product and security work separate (Priority: P2)

**Goal**: This change set does not rewrite engine behavior, CI policy, or the README-accuracy PR.

**Independent Test**: `git diff origin/master -- src/trade_risk_engine .github/workflows/ci.yml` is empty. Diff does not include `specs/001-readme-accuracy-and-feature-reconciliation/`.

### Implementation for User Story 3

- [X] T009 [P] [US3] Confirm `src/trade_risk_engine/` has no diff versus `origin/master` (empty `git diff origin/master -- src/trade_risk_engine`)
- [X] T010 [P] [US3] Confirm `.github/workflows/ci.yml` has no diff versus `origin/master` (CON-001 install line and `safety check` job unchanged)
- [X] T011 [US3] Confirm this branch does not modify files under `specs/001-readme-accuracy-and-feature-reconciliation/` or the PR #34 worktree `/home/nick/dev/verdict-risk/.worktrees/001-readme-accuracy`

**Checkpoint**: Compatibility lane is isolated from product and security-tooling lanes.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Repository-native checks and disclosure that remaining CI failures are not this feature

- [X] T012 Run `ruff check src tests`, `ruff format --check src tests`, `mypy src`, and `pytest tests -q` using `pyproject.toml` in this worktree
- [X] T013 Follow `specs/002-cross-repo-contract-compat/quickstart.md` end to end and keep the named SHA in `producer-revision.txt` consistent with the written declaration
- [X] T014 Record in `specs/002-cross-repo-contract-compat/repair-path.md` that the CI security job remains a separate lane and that a green CON-001 result is not a merge

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on T001
- **User Story 1**: Depends on Phase 2; T004 must fail before T005
- **User Story 2**: Depends on T001 (SHA) and can start after Phase 2; does not need T005
- **User Story 3**: Independent of the JSON rewrite; can run after Setup
- **Polish**: Depends on US1–US3 as delivered

### User Story Dependencies

- **User Story 1 (P1)**: After Foundational. MVP.
- **User Story 2 (P1)**: After Foundational. Can run in parallel with US1 (different files: `repair-path.md` vs `.verdict/compat-manifest.json` / `tests/test_compat_manifest.py`).
- **User Story 3 (P2)**: After Setup. Parallel with US1/US2 (read-only diffs).

### Parallel Opportunities

- After T003: T004 (tests) then T005; T008 (repair-path.md); T009 and T010 in parallel
- Do not parallelize two writers on `.verdict/compat-manifest.json` or `tests/test_compat_manifest.py`

### Parallel Example: After Foundational

```bash
# Sequential for US1 (same files):
Task: T004 failing tests in tests/test_compat_manifest.py
Task: T005 replace .verdict/compat-manifest.json

# Parallel with US1 (different files):
Task: T008 write specs/002-cross-repo-contract-compat/repair-path.md
Task: T009 git diff origin/master -- src/trade_risk_engine
Task: T010 git diff origin/master -- .github/workflows/ci.yml
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. T001–T003 name and install the producer
2. T004 fail, T005 emit, T006–T007 check and tests
3. Stop and validate `verdict compat check` allowed

### Incremental Delivery

1. Setup + Foundational
2. US1 declaration rewrite (MVP)
3. US2 recorded path
4. US3 isolation proof
5. Polish native checks; disclose security job still failing

### Parallel Team Strategy

One writer in this worktree. Do not staff parallel writers. US2/US3 file-disjoint tasks may be sequenced in one owner, not two checkouts.

---

## Notes

- [P] tasks = different files, no incomplete dependencies
- Do not change `.github/workflows/ci.yml` or `src/trade_risk_engine/`
- Do not merge PR #34 from this lane
- Unknown or failed compat check = blocked, not guessed
- Next command after this file is `/speckit-analyze`, then `/speckit-implement`

---

## Phase 7: Convergence

- [X] T015 Resolve the `verdict` CLI via PATH (CI installs it globally before pytest) with fallback to `.venv/bin/verdict` in `tests/test_compat_manifest.py` per Constitution IV / SC-001 / plan: testing (partial)
