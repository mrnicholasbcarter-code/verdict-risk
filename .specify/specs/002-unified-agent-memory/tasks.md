---
description: "Task list for Unified Agent Memory, Session Recall, and Documentation Enforcement"
---

# Tasks: Unified Agent Memory, Session Recall, and Documentation Enforcement

**Input**: Design documents from `.specify/specs/002-unified-agent-memory/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included. The spec does not request TDD generally, but two failure modes have **no
recovery path** — an indexed credential (FR-014) and a blocking gate with no way through
(FR-019a). Tests for those are not optional. Other test tasks are scoped to contract
verification only.

**Organization**: Grouped by user story. Each story is independently implementable and
testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1–US4, mapping to spec.md user stories

## Path Conventions

All authored code lives in a **new child repository** `/home/nick/dev/agent-memory/`
(plan.md Structure Decision — `~/.claude/` is not version controlled, so nothing there can
bind evidence to a commit). Paths below are relative to that repo unless absolute.

Locations touched by configuration only, never by authored logic:

- `~/.claude/settings.json` — hook wiring, absolute paths and matchers, no logic
- `/home/nick/.basic-memory-pilot/notes/` — capture output
- `~/.claude/.docs-receipts/` — existing receipt scheme, unchanged

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the repository boundary required by Constitution Principles III and IV.

- [X] T001 Create child repo at `/home/nick/dev/agent-memory/` with `git init`, and confirm the workspace root `/home/nick/dev` is still not a git repo
- [X] T002 [P] Create `/home/nick/dev/agent-memory/package.json` with `"type": "commonjs"`, `"private": true`, `"scripts": {"test": "node --test tests/"}`, and **zero dependencies**
- [X] T003 [P] Create `/home/nick/dev/agent-memory/.gitignore` excluding `node_modules/`, `*.log`, and `fixtures/*.local.*`
- [X] T004 [P] Create directory skeleton `hooks/`, `lib/`, `config/`, `tests/`, `scripts/`, `fixtures/` under `/home/nick/dev/agent-memory/`
- [X] T005 Verify the runner works: `cd /home/nick/dev/agent-memory && node --test tests/` exits 0 on an empty suite

**Checkpoint**: A versioned home exists for every artifact.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared libraries and the verified baseline. Every user story depends on these.

**⚠️ CRITICAL**: No user story work begins until this phase completes.

- [X] T006 Record the prerequisite baseline from quickstart.md into `/home/nick/dev/agent-memory/fixtures/baseline.json`: basic-memory config identical in `~/.codex/config.toml` and `~/.claude.json`, watcher `running: true`, docs endpoint reachable, transcript file count and total size, and the `entity` / `search_index` row counts from `memory.db`
- [X] T007 Implement `lib/redact.cjs` exporting `redact(text)` and `containsSecret(text)`, with rules for `ANTHROPIC_AUTH_TOKEN` (confirmed present: 641 occurrences across 32 files, **152 with a real value across 25 files**) plus defensive rules for `sk-ant-*`, `ghp_*`, `gho_*`, `AKIA*`, `Bearer <…>`, PEM blocks, JWTs (all 0 hits today). Mask as `⟨redacted:<rule-id>⟩` per FR-014c
- [X] T008 [P] Write `tests/redact.test.cjs`: each rule masks its pattern; masked output no longer matches any rule; `containsSecret` is true on unmasked input and false after masking; a value is never emitted in full
- [X] T009 Create `fixtures/sessionend-with-token.json` — a synthetic `SessionEnd` payload plus a synthetic transcript containing a **fake** token of realistic shape (35 chars). **Never copy a real value from `~/.claude/projects/`**
- [X] T010 Implement `lib/note.cjs` rendering a note per `contracts/knowledge-note.schema.md`: frontmatter (`title`, `type`, `status`, `provenance`, `observed_at`, `confidence`, `tags`), body sections, and `[[permalink]]` relations
- [X] T011 [P] Write `tests/note.test.cjs`: `type` outside the five-value enum is rejected; `confidence: verified` without `evidence` is rejected; `type: decision` without `rationale` is rejected (FR-005a, FR-005c)

**Checkpoint**: Redaction and note rendering are proven. User stories can begin in parallel.

---

## Phase 3: User Story 1 — Cross-client shared knowledge (Priority: P1) 🎯 MVP

**Goal**: A durable record written in one client is retrievable from a fresh session of the
other, with conflicts surfaced rather than silently resolved.

**Independent Test**: Record a decision in Claude Code. Start a fresh Codex session. Search
for it. It returns with frontmatter intact. Then write a contradicting record and confirm
**both** come back flagged, with neither deleted and no recency-based winner.

**No new infrastructure is needed.** `~/.claude.json:962-978` and `~/.codex/config.toml:113-119`
already run the same basic-memory `0.22.1` server against the same `pilot` project with
`BASIC_MEMORY_CONFIG_DIR=/home/nick/.basic-memory-pilot`. This story is convention plus
validation plus an operator CLI.

### Implementation

- [X] T012 [US1] Implement `lib/knowledge.cjs` `writeRecord()` in `/home/nick/dev/agent-memory/lib/knowledge.cjs`: validate against the four FR-005a classes (`decision`, `verified-fact`, `refuted-claim`, `correction`), require origin per FR-004, and **refuse to overwrite an existing permalink** — `write_note` errors by default (`write_note_overwrite_default: false`) and there is no versioning
- [X] T013 [US1] Implement `supersede()` and `dispute()` in `lib/knowledge.cjs`: `supersede` writes the new note with a `supersedes` relation and edits the old to `status: superseded` with `superseded_by`; `dispute` marks **both** `disputed` and links them with `contradicts`. **Both notes are always retained** (FR-006, FR-006b)
- [X] T014 [P] [US1] Write `tests/knowledge.test.cjs`: writing to an existing permalink throws; `supersede` leaves the old note on disk; `dispute` marks both and picks no winner, **including when one is newer** (FR-006)
- [X] T014a [US1] Add conflict-consumption rules to both clients' always-loaded instruction files (FR-006a): on receiving a `status: disputed` pair, verify against source, runtime, or live inspection before acting on either record or writing a resolution; if reality cannot be checked in that session, act on neither and state the uncertainty
- [X] T014b [P] [US1] Extend `tests/knowledge.test.cjs` in `/home/nick/dev/agent-memory/tests/knowledge.test.cjs`: a disputed pair is returned intact with both members flagged, and no code path picks a winner or deletes either (FR-006b)
- [X] T015 [US1] Implement the operator CLI `scripts/knowledge.cjs` with `list`, `show`, `write`, `supersede`, `dispute`, and `remove` subcommands, satisfying FR-009 ("see what was captured and remove any record")
- [X] T016 [US1] Add shared-store usage instructions to `/home/nick/CLAUDE.md`: what belongs in the shared store (the four FR-005a classes), what does **not** (FR-005b — anything derivable from the repo or git history), that a candidate is written **at the point of observation** rather than at session end (FR-007a), and that `search_type` must be passed explicitly for precision-sensitive queries
- [X] T017 [P] [US1] Add the equivalent instructions to the Codex always-loaded instruction file, so neither client reads the other's private memory (FR-002)
- [X] T018 [US1] Verify FR-003: confirm the shared store writes nothing into either client's own index, and assert `~/.claude/projects/-home-nick-dev/memory/MEMORY.md` is within its **200-line / 25 KB** budget
- [X] T019 [US1] Run quickstart Scenario 1 (cross-client retrieval) and Scenario 2 (conflict surfaced, not resolved) and record results

**Checkpoint**: US1 is independently functional. **This is the MVP** — it delivers the
original goal the failed symlink bridge was reaching for.

---

## Phase 4: User Story 2 — Recall across past sessions (Priority: P2)

**Goal**: Knowledge from any past session is searchable by meaning from either client, with no
age cutoff, and no secret ever enters the index.

**Independent Test**: Ask about a topic discussed only in a session from the oldest day in the
corpus (2026-08-18). The answer returns with a pointer that resolves to the source session and
carries its date.

### Tests for User Story 2 ⚠️ NOT OPTIONAL

> T021 and T022 gate everything else in this phase. There is **no recovery path** if a secret
> reaches the index: `embed: false` excludes semantic indexing only and leaves content fully
> present in FTS (`search_service.py:741-763`). Run these before wiring anything.

- [X] T020 [P] [US2] Write `tests/transcript.test.cjs`: projection selects `isCompactSummary` user records, human prompts (`type:"user"` **without** `toolUseResult` and **without** `isCompactSummary`), and assistant `text` blocks; excludes `toolUseResult`, `attachment`, `tool_use`, `thinking`; asserts roles are read from `.message.role` **not** top-level; asserts a selector keyed on `type:"summary"` matches **nothing** (0 hits across 60 files — the field is `isCompactSummary`)
- [X] T021 [US2] Write `tests/session-capture.contract.test.cjs` case T1: a transcript containing the fixture token produces output containing `⟨redacted:` and **zero** occurrences of the value
- [X] T022 [US2] Write contract test case T2: a projection that still matches a rule after redaction results in **nothing written** and a non-zero exit (fail closed)
- [X] T023 [P] [US2] Write contract test cases T3–T7: 0 compaction summaries still yields a note; unparseable final line is skipped; existing target exits 0 unmodified; interrupted write leaves no partial `.md`; an 11.8 MB transcript yields ≈8% of input bytes with no `toolUseResult` content

### Implementation for User Story 2

- [X] T024 [US2] Implement `lib/transcript.cjs` `project(path)` in `/home/nick/dev/agent-memory/lib/transcript.cjs` — parse line-delimited JSON, skip unparseable lines, select the three inputs. **All three are required**: compaction summaries appear in only **44 of 233** transcripts, so summaries alone would leave 189 sessions unrecallable (FR-010a)
- [X] T025 [US2] Implement `hooks/session-capture.cjs` per `contracts/session-capture-hook.md`: read `transcript_path` from stdin (never derive it), project → redact → render → write to `/home/nick/.basic-memory-pilot/notes/sessions/`. Write to a temp file in the same directory then `rename()`; the watcher debounces at 1000 ms and would otherwise index a partial file. Never overwrite. Emit no stdout, exit 0
- [X] T026 [US2] Make `hooks/session-capture.cjs` executable and confirm the `sessions/` folder name has **no leading dot** — the watcher skips any path part starting with `.` relative to the project root
- [X] T027 [US2] Implement `scripts/backfill.cjs` to run the projection over all `~/.claude/projects/**/*.jsonl` (233 files, 194 MiB), skipping any transcript whose note already exists
- [X] T028 [US2] Back up `~/.claude/settings.json` to `~/.claude/settings.json.bak-<UTC timestamp>` first, per the D-04 precedent, then wire the `SessionEnd` hook into `~/.claude/settings.json` per the contract: `type: "command"`, absolute path, `async: true`, and **no matcher**. Omitting the matcher removes the dependency on the unverified termination-reason field name (open item O-2)
- [X] T029 [US2] Verify `async` placement by timing a session exit — a perceptible pause means `async` was omitted or misplaced. It is a **command-hook-only** field, a sibling of `type` and `command` in the inner `hooks` array
- [X] T030 [US2] Run the backfill, then assert no secret reached the index: `SELECT count(*) FROM search_index WHERE content LIKE '%<prefix>%'` returns **0** for each confirmed token prefix
- [X] T031 [US2] **Resolve open item O-1**: measure recall latency at full corpus scale and record the number in quickstart.md Scenario 5. The 0.106 s reference figure was measured against a near-empty store (6 entities) and **SC-004 must not be marked met until this is measured**
- [X] T032 [US2] Verify FR-011 and FR-011a: every recall result carries a pointer resolving to its source session and that session's date. Confirm `session_id` → path is a plain string join, since the transcript path is `<slug>/<sessionId>.jsonl`
- [X] T033 [US2] Verify FR-012 (new sessions searchable with no manual reindex), FR-013 (reports "nothing found" rather than unrelated material), and FR-014a (original transcripts unmodified — checksum a sample before and after)
- [X] T033a [US2] Verify FR-015 from Codex: run the Scenario 3 recall query through the Codex client against the same store and confirm equivalent results, pointer, and session date. Pass `search_type` explicitly (the service layer falls back to FTS when no mode is supplied)
- [X] T034 [US2] Run quickstart Scenarios 3, 4, and 5 and record results

**Checkpoint**: US1 and US2 both work independently.

---

## Phase 5: User Story 3 — Enforced docs-before-change with a viable path through (Priority: P3)

**Goal**: Changes to a covered territory require documentation consultation, and an in-session
docs query satisfies the gate.

**Independent Test**: With the gate active, attempt a change in a covered territory with no
prior lookup — it is denied with a hint that actually resolves. Perform the named lookup.
Retry — it proceeds.

**⚠️ Sequencing is mandatory (D-05)**: index the corpus → teach the gate to accept an MCP
query as a receipt → wire the gate. Wiring first is a self-inflicted outage. T046 must not run
before T045.

### Implementation for User Story 3

- [X] T035 [US3] Migrate `~/.claude/hooks/docs-gate.cjs` to `/home/nick/dev/agent-memory/hooks/docs-gate.cjs` **byte-identical**, and commit that alone so the behavioural change is reviewable on its own diff
- [X] T036 [US3] Create `config/territories.json` validating against `contracts/territories.schema.json`: `packageTerritories.mode: "allowlist"`, `omniroute` with `enforced: true`, `zod` with `enforced: false` (indexed but not yet enforced, per FR-019b)
- [X] T037 [US3] Change C2 — replace the inline `TERRITORIES` const at `docs-gate.cjs:21-25` with a load of `config/territories.json`. **This is what satisfies FR-022**, which is unsatisfied today because territories are enforcement logic, not configuration. Malformed or unrecognised-version input must throw, which `:168` converts to `ask`
- [X] T038 [US3] Change C3 — constrain the `PKG_RE` fall-through at `:27` to the allowlist. `ownerOf` (`:32-40`) currently makes **any** `**/node_modules/<pkg>` path a territory owned by `<pkg>`, so the real enforced surface is three directories **plus every installed package** against **two** indexed libraries. **Without C3, FR-019b's "`omniroute` alone" is unreachable no matter what the territory list says**
- [X] T039 [US3] Change C4 and C5 — remove `ruflo` and bare `claude-flow` entirely (FR-020; neither is declared or installed) and anchor every remaining pattern. The existing `claude-flow` pattern `(^|\/)\.claude-flow(\/|$)` is **unanchored** and matches `/home/nick/dev/.specify/.claude-flow`, which exists on disk, producing a denial whose only hint is `claude-flow --help` — a command that cannot run
- [X] T040 [US3] Change C1 — add the MCP receipt branch in `receipt` mode after the Bash branch (`~:143`), matching `/^mcp__docs-mcp-server__/` and keying the receipt on **`tool_input.library`**. Read the **input, not the result**: `search_docs` returns plain prose with no structured library field
- [X] T041 [US3] Verify FR-018 — every denial reason names an action that resolves, and `docHints()` never emits a command or path that does not exist
- [X] T042 [P] [US3] Write `tests/docs-gate.contract.test.cjs` cases T1–T3: empty stdin → `ask`; unparseable JSON → `ask`; missing `territories.json` → `ask`. **None may emit nothing** — a silent pass is a fail-open bug that blocks the feature (FR-021)
- [X] T043 [P] [US3] Write contract test cases T4, T5, T8, T9, T10: denial without a receipt; pass after an observed MCP query; pass for an `enforced: false` territory; config listing `ruflo` throws → `ask`; MCP call with no `library` passes and writes no receipt
- [X] T044 [US3] Write contract test cases T6 and T7 — the outage regression tests: a write under an unlisted `node_modules/<pkg>` **passes** (proves C3), and a write under `/home/nick/dev/.specify/.claude-flow` **passes** (proves C4). Assert on stdout being empty, not on exit code — `deny` also exits 0 (`:95-101`)
- [X] T045 [US3] Index documentation for `omniroute` via `mcp__docs-mcp-server__scrape_docs`, poll `list_jobs` to completion, and confirm via `list_libraries`. **Record the indexing duration — this resolves open item O-4.** Satisfies FR-019 and SC-006: no territory is enforced before its docs are consultable
- [X] T046 [US3] Back up `~/.claude/settings.json` to a fresh `~/.claude/settings.json.bak-<UTC timestamp>` first, then wire `PreToolUse` (mode `check`) and `PostToolUse` (mode `receipt`) into `~/.claude/settings.json`. The MCP matcher **must be `mcp__docs-mcp-server__.*`** — the trailing `.*` is required, since a matcher without it is compared as an exact string and matches no tool
- [X] T047 [US3] Verify T046 fires for real rather than only when piped by hand: perform a live `search_docs` call and confirm a receipt appears under `~/.claude/.docs-receipts/<session_id>/`
- [X] T048 [US3] Document the immediate-disable procedure (FR-023) in `/home/nick/dev/agent-memory/README.md`. This is the only escape hatch — FR-019a permits no advisory mode and no per-invocation override. Document the revert alongside it: restore the most recent `~/.claude/settings.json.bak-*`. That file is outside every git repo, so the backup is the only recovery path. Also document the FR-019c expansion procedure — territories are added one at a time, each only after the previous one has been enforced without an unsatisfiable denial
- [X] T049 [US3] Run quickstart Scenarios 6, 7, and 8 and record results

**Checkpoint**: Enforcement is blocking, covers `omniroute` only, and has a working path through.

---

## Phase 6: User Story 4 — Honest inventory of the flow stack (Priority: P4)

**Goal**: No live configuration instructs an agent to invoke something that is not installed.

**Independent Test**: Cross-check every component named in configuration against its actual
install status. Zero mismatches.

**⚠️ This is the largest work item in the feature**, not the cleanup it was scoped as. **183
live files** reference tooling that is neither declared nor installed.

### Implementation for User Story 4

- [X] T050 [US4] Implement `scripts/inventory-flow-refs.sh` emitting a per-component table of declared / installed / binaries / live reference count, satisfying FR-024
- [X] T051 [P] [US4] **Resolve open item O-3** — verify whether `@claude-flow/aidefence` and `@claude-flow/guidance` are declared in any `package.json` and present in `node_modules`, and record the result. Both are currently UNVERIFIED
- [X] T052 [US4] Produce a categorised triage of the 183 referencing files into `/home/nick/dev/agent-memory/docs/flow-stack-triage.md`: ~130 slash commands under `.claude/commands/**`, 20 `.claude/skills/*/SKILL.md`, 8 agents under `.claude/agents/{core,swarm}/*`, 30+ `.claude/helpers/*` (including `ruflo-hook.cjs`), plus `.claude/proven-config.json` and `.claude/statusline.sh`. Note that **no live `settings.json` invokes `.claude/helpers/**`** — those are orphaned and reachable only if a command or skill body tells an agent to run them
- [X] T053 [US4] ⚠️ **DECISION GATE — resolve open item O-5.** Present the triage to the operator and obtain a delete-vs-rewrite disposition **per category**. Do not proceed to T054 without it. Deleting ~130 slash commands is irreversible and is explicitly not a call to make unilaterally
- [X] T054 [US4] Execute the agreed dispositions from T053, one category per commit so each is independently revertible
- [X] T055 [US4] Verify SC-007: re-run `scripts/inventory-flow-refs.sh` and confirm **zero** live references to components that are not installed
- [X] T056 [US4] Confirm the retained components are correctly recorded: `@claude-flow/codex`, `agentic-flow`, `ruvector`, and the `@ruvector/*` packages are real and installed — noting `ruvector` arrives **transitively via `agentic-flow`**, not as a direct dependency
- [X] T057 [US4] Run quickstart Scenario 9 and record results

**Checkpoint**: All four user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T058 [P] Update `spec.md` Verified Current State and Known-False Claims with everything learned during implementation, satisfying FR-026 (these sections are maintained, not frozen)
- [X] T059 [P] Update `research.md` open items O-1 through O-5 with their resolutions
- [X] T060 Re-run the Constitution Check in `plan.md` against the delivered implementation and confirm Principles III and IV are now genuinely satisfied by the committed repo
- [X] T061 Assess SC-010 — can the operator answer "what do my agents remember about X, and where did it come from?" using only `scripts/knowledge.cjs` and search
- [X] T062 Dogfood the shared store: record this feature's own decisions as `decision` records and its refuted premises (the symlink bridge; store-based docs verification; `ruflo` as a territory) as `refuted-claim` records with evidence
- [ ] T063 Assess SC-002 after a week of both clients writing — confirm each client's own index stayed valid and within budget
- [X] T064 Assess SC-003 — sample 10 topics discussed in past sessions and confirm recall returns relevant material for at least 9
- [X] T064a Assess FR-007b: sample 10 completed sessions, count the FR-005a-class knowledge each produced against what was actually written to the shared store, and record the capture rate. An unmeasured rate MUST NOT be reported as satisfying FR-007
- [X] T065 Final: confirm every quickstart scenario has a recorded result, that **SC-004 is marked met only if T031 measured it at corpus scale**, and that every criterion SC-001 through SC-010 carries an explicit **met / unmet / unmeasured** verdict — per the constitution's Quality Gates rule, an unmeasured criterion MUST NOT be reported as met

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — **blocks all user stories**
- **US1 (Phase 3)**: depends on Phase 2. No dependency on other stories
- **US2 (Phase 4)**: depends on Phase 2, and on T007/T010 specifically. Independent of US1
- **US3 (Phase 5)**: depends on Phase 1 only — it touches a different file with no shared library. Can start immediately after Setup if staffed separately
- **US4 (Phase 6)**: depends on Phase 1 only. Fully independent
- **Polish (Phase 7)**: depends on all desired stories

### Critical ordering constraints

| Constraint | Why |
|---|---|
| T007 before T024/T025 | Redaction must exist before anything writes a projection |
| T021, T022 before T028 | Never wire capture before the fail-closed secret tests pass |
| T045 before T046 | **D-05** — index docs before wiring the gate, or enforcement is an outage |
| T038 before T046 | Without the `PKG_RE` constraint, wiring blocks every package directory |
| T053 before T054 | Operator decision gate; deletions are irreversible |
| T031 before T065 | SC-004 cannot be marked met on an unmeasured target |

### Parallel Opportunities

- T002, T003, T004 in parallel (Setup)
- T008 and T011 in parallel (Foundational tests, different files)
- **US3 and US4 can run fully in parallel with US1 and US2** — different files, no shared libraries
- Within US2: T020 and T023 in parallel
- Within US3: T042, T043 in parallel; T044 is separate because it asserts on the outage cases

---

## Parallel Example: post-Foundational fan-out

```bash
# Three independent tracks once Phase 2 completes:
Track A (US1 → US2): T012 → T019, then T020 → T034
Track B (US3):       T035 → T049   # only needs Phase 1
Track C (US4):       T050 → T052, then STOP at the T053 decision gate
```

**One worktree per writing agent, explicit file ownership** — Track B is the only track that
touches `hooks/docs-gate.cjs`, Track A the only one touching `lib/` and
`hooks/session-capture.cjs`.

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup
2. Phase 2: Foundational
3. Phase 3: US1
4. **STOP and VALIDATE** — quickstart Scenarios 1 and 2
5. This alone delivers the original goal the symlink bridge failed at

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → cross-client sharing works (**MVP**)
3. US2 → past sessions become recallable
4. US3 → docs enforcement, blocking but survivable
5. US4 → configuration stops lying about what is installed

### Risk-ordered note

US4 is last by priority but holds the **largest** effort and the only irreversible step
(T054). Starting its read-only tasks (T050–T052) early in parallel is cheap and surfaces the
T053 decision sooner.

---

## Notes

- `[P]` = different files, no dependencies
- Commit after each task or logical group; one category per commit in T054
- This feature installs **no new dependency**. Every consumed service already runs
- Two failure modes have no recovery path: an indexed credential (T021, T022) and a gate that
  blocks with no way through (T044). Neither test is optional
- Verify against live behaviour, not memory — several premises in the spec were already
  corrected by research, and more may be
