# Implementation Plan: Unified Agent Memory, Session Recall, and Documentation Enforcement

**Branch**: `002-unified-agent-memory` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `.specify/specs/002-unified-agent-memory/spec.md`

## Summary

Consolidate three disconnected memory stores, an unindexed transcript corpus, and an unwired
documentation gate into one governed design, on top of infrastructure that already exists and
is already shared.

The primary requirement is **durable, cross-client knowledge that survives a session** — a
decision recorded in Claude Code must be retrievable from Codex, and a fact verified eight
days ago must be recallable today.

The technical approach is deliberately additive and uses no new services:

1. **Shared layer** — the running basic-memory MCP `pilot` project, already configured
   identically in both `~/.claude.json` and `~/.codex/config.toml`. Nothing to install.
2. **Capture** — an `async: true` `SessionEnd` command hook that projects the transcript to
   redacted markdown and writes it into the watched notes directory. The running filesystem
   watcher indexes it in ~1 s. Fire-and-forget, so it can never block or slow work (FR-008).
3. **Enforcement** — three surgical changes to the existing working `docs-gate.cjs`:
   externalise the territory list, shrink the enforced set to an allowlist of territories
   that actually have indexed documentation, and add one branch that accepts an observed
   `mcp__docs-mcp-server__*` call as a receipt.
4. **Inventory** — remove `ruflo` and bare `claude-flow` from live configuration, since
   neither is installed and both are still referenced by 183 files.

The single largest risk is not the new code. It is item 4, and the fact that the existing gate
treats **every installed npm package** as a documentation territory (research R5) while the
docs corpus contains **two libraries**.

## Technical Context

**Language/Version**: Node.js (CommonJS `.cjs`) — matches the existing `docs-gate.cjs`; hooks
are invoked as bare executables by Claude Code and must start fast, ruling out a runtime that
needs a project context.

**Primary Dependencies**: None added. All consumed infrastructure is already installed and
running — basic-memory MCP `0.22.1` (via `uvx`), its filesystem watcher (pid 2339371),
docs-mcp-server (Docker, SSE `localhost:6280`), Claude Code hooks, Codex MCP client.

**Storage**:

- Shared knowledge — basic-memory `pilot` project, `BASIC_MEMORY_CONFIG_DIR=/home/nick/.basic-memory-pilot`;
  markdown notes on disk plus SQLite (`memory.db`, FTS5 `search_index` + `vec0 float[384]`
  `search_vector_embeddings`).
- Recall substrate — `~/.claude/projects/**/*.jsonl` (read-only; never modified).
- Receipts — `~/.claude/.docs-receipts/<session_id>/<tool>` (existing scheme, unchanged).
- Territory config — a new JSON file read by the gate at startup.

**Testing**: Node's built-in `node:test` runner with `node:assert` — no new dependency, and
the units under test are pure functions (redaction, projection, ownership resolution) plus
stdin/stdout contract tests that pipe a JSON payload to a hook and assert on stdout JSON.

**Target Platform**: Linux (`6.17.0-1022-gcp`), single-user machine-local configuration.
Both clients run as user `nick` on the same host — this is what makes a filesystem-mediated
shared layer viable at all.

**Project Type**: Agent tooling / configuration — hook executables plus a config file. Not an
application; no service, no API, no UI.

**Performance Goals**:

- Capture must add **0 ms** to the blocking path (`async: true`, fire-and-forget).
- Recall p50 target ~0.106 s, taken from the 2026-08-19 hybrid-retrieval benchmark
  (research R1). **This figure was measured against a near-empty store and is not yet a
  validated target at corpus scale** — see Constitution Check, and open item O-1.
- Gate decision must stay well inside the `PreToolUse` timeout; the current gate does no I/O
  beyond a receipt `existsSync`, and the change adds one file read.

**Constraints**:

- Secrets MUST be masked **before** content reaches the index (FR-014). This is not a
  preference: `embed: false` in basic-memory excludes semantic indexing only and leaves
  content in FTS (research R2), so there is no after-the-fact removal.
  `ANTHROPIC_AUTH_TOKEN` appears with a real value 152 times across 25 files (research R3).
- Non-markdown files are indexed as **metadata only** — content must be converted, not
  dropped in (research R2).
- No path component under the notes root may begin with `.` or the watcher skips it
  (research R2).
- Enforcement must be blocking with no per-invocation override (FR-019a), so the covered
  territory set must be an allowlist, not the current fall-through.
- `~/.claude/` is **not version controlled** — see Complexity Tracking.

**Scale/Scope**: 8 project dirs · 233 transcripts · 194 MiB · growing ~24 MB/day (~8.7 GB/yr).
Curated projection is ~8% of corpus bytes. 183 files reference absent tooling. Shared store is
effectively empty today (6 entities, 48 FTS rows).

## Constitution Check

*Gates evaluated against `.specify/memory/constitution.md` v1.1.0. Per the Quality Gates
evidence-disclosure rule, unknown and unavailable results are named as such below and are not
reported as passing.*

### Initial evaluation (pre-Phase 1)

| Principle | Verdict | Evidence |
|---|---|---|
| **I. Coordination Is Governance** | **PASS** | Single-owner feature, one worktree, no concurrent writers. Spec-kit is the record; artifacts under `.specify/specs/002-unified-agent-memory/`. |
| **II. Documentation Before Dependencies** | **PASS** | Every load-bearing claim in `research.md` cites source, schema, live output, or official docs. Three claims taken from a subagent were independently re-verified against `code.claude.com/docs/en/hooks.md`, correcting a 18-event list to the actual 31 and confirming `SessionEnd`. No new dependency is introduced, so there is nothing further to read up on. |
| **III. Repository Boundaries** | **CONDITIONAL** | Implementation artifacts target `~/.claude/`, which belongs to no repository. Resolved in Structure Decision by authoring them in a new child repo and referencing by absolute path. Tracked in Complexity Tracking. |
| **IV. Verification Is Part of the Change** | **CONDITIONAL** | Cannot bind evidence to a commit while the artifacts live only in unversioned `~/.claude/`. Same resolution as III. Additionally SC-004's latency target is inherited from a benchmark against a near-empty store — **disclosed as unvalidated**, not claimed as met. |

### Post-Phase 1 re-evaluation

| Principle | Verdict | Change from initial |
|---|---|---|
| **I** | **PASS** | Unchanged. |
| **II** | **PASS** | Phase 1 added no dependency. Contracts are derived from observed payloads and the published hook schema, not from inference. |
| **III** | **PASS** | Resolved. Structure Decision places all authored artifacts in one new child repo that owns its own `.git`; `~/.claude/settings.json` references them by absolute path and holds no logic. |
| **IV** | **PASS with open evidence** | Versioned artifacts and honest disclosures are present. O-1 remains unresolved because the active SQLite process lacks `vec0`; SC-004 stays unmeasured. |

**No governance gate is failed. Principle IV retains open evidence items: vector recall and stale-index cleanup are not reported as passing.**

## Project Structure

### Documentation (this feature)

```text
.specify/specs/002-unified-agent-memory/
├── plan.md              # This file
├── research.md          # Phase 0 output — verified findings R1..R7 + open items
├── data-model.md        # Phase 1 output — entities, fields, states, validation
├── quickstart.md        # Phase 1 output — runnable validation scenarios
├── contracts/           # Phase 1 output — hook and config contracts
│   ├── session-capture-hook.md
│   ├── docs-gate-hook.md
│   ├── territories.schema.json
│   └── knowledge-note.schema.md
├── checklists/
│   └── requirements.md  # 16/16 passing
└── tasks.md             # Phase 2 — NOT created by /speckit-plan
```

### Source Code

A new child repository, `agent-memory/`, owns every authored artifact. It exists because no
current child repo owns agent configuration and `~/.claude/` is not version controlled.

```text
/home/nick/dev/agent-memory/          # new child repo, owns its own .git
├── hooks/
│   ├── session-capture.cjs           # SessionEnd, async:true — projects + redacts + writes
│   └── docs-gate.cjs                 # migrated from ~/.claude/hooks/, then modified
├── lib/
│   ├── redact.cjs                    # secret detection + masking (pure)
│   ├── transcript.cjs                # .jsonl → curated projection (pure)
│   └── note.cjs                      # projection → basic-memory markdown + frontmatter
├── config/
│   └── territories.json              # externalised territory list (satisfies FR-022)
├── tests/
│   ├── redact.test.cjs
│   ├── transcript.test.cjs
│   ├── docs-gate.contract.test.cjs   # pipes stdin JSON, asserts stdout decision
│   └── session-capture.contract.test.cjs
└── scripts/
    └── inventory-flow-refs.sh        # enumerates the 183 references for FR-025 triage
```

Referenced-but-not-owned locations (touched by configuration only, never by authored logic):

```text
~/.claude/settings.json                       # hook wiring — absolute paths into agent-memory/
~/.claude/hooks/docs-gate.cjs                 # removed after migration
/home/nick/.basic-memory-pilot/notes/sessions/ # capture output; no dot-prefixed path parts
~/.claude/.docs-receipts/<session_id>/        # unchanged receipt scheme
```

**Structure Decision**: All authored logic lives in a **new child repository
`/home/nick/dev/agent-memory/`**, which owns its own `.git` per Constitution Principle III.
`~/.claude/settings.json` is reduced to wiring — absolute paths and matchers only, no logic —
so that everything reviewable is versioned and every verification run binds to a commit
(Principle IV). `docs-gate.cjs` is **migrated, then modified**, as two separate commits, so
the migration diff is empty-by-content and the behavioural change is reviewable on its own.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| **A new child repository** rather than reusing an existing one | Constitution Principles III and IV require a repository boundary and commit-bound evidence. Eleven child repos exist and none owns agent configuration; `~/.claude/` and the `/home/nick/dev` workspace root are both non-repositories. | *Author in `~/.claude/hooks/` directly* — leaves all logic unversioned, so no verification can be bound to a commit and Principle IV cannot be met. *Add to an existing repo (e.g. `verdict-core`)* — puts machine-local agent config inside an unrelated product repo, violating Principle III more severely than creating a correct boundary. |
| **Shrinking gate coverage to an explicit allowlist**, diverging from the current fall-through | Research R5 found `PKG_RE` makes **every** `**/node_modules/<pkg>` path a territory. With blocking enforcement (FR-019a) and two indexed libraries, wiring the gate unchanged is a guaranteed self-inflicted outage on the first write into any package directory. | *Wire the gate as-is* — the spec's own D-05 names this "a self-inflicted outage". *Keep the fall-through but warn instead of deny* — FR-019a forbids an advisory phase. The allowlist is the only shape that is blocking, safe, and growable one territory at a time per FR-019b. |
| **Three inputs to the transcript projection** (compaction summaries + human prompts + assistant prose) instead of one | Only **44 of 233** transcripts contain a compaction summary (research R3); summaries alone leave 189 sessions unrecallable, failing FR-010a's no-cutoff requirement. | *Summaries only* — 81% of sessions invisible. *Raw lines* — 79% of bytes are tool traffic, against a corpus growing 24 MB/day. |

### Note on FR-019b

The spec states the initial covered set is `omniroute` alone. Research R5 shows this is **not
achievable by editing the territory list**, because `PKG_RE` grants ownership by path pattern
independently of that list. Satisfying FR-019b therefore requires constraining `PKG_RE` to the
allowlist as well. This is a plan-level correction to a spec premise, recorded here rather
than silently absorbed; it changes no requirement, only what the implementation must touch to
meet one.

### Note on FR-025

FR-025 was scoped in the spec as cleanup. The inventory found **183 live files** referencing
absent tooling (research R7). It is the largest work item in the feature and needs an operator
decision on delete-vs-rewrite per category before tasks can be sized. Carried as open item
O-5.
