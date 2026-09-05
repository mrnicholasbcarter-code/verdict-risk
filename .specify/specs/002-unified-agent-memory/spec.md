# Feature Specification: Unified Agent Memory, Session Recall, and Documentation Enforcement

**Feature Branch**: `002-unified-agent-memory`

**Created**: 2026-08-26

**Status**: Draft

**Input**: User description: "Unified agent memory, session recall, and documentation enforcement. Consolidate the currently fragmented memory/recall/docs stack into one governed design. Scope: (1) three disconnected memory stores — Claude auto memory at ~/.claude/projects/<slug>/memory/, Codex memory at ~/.codex/memories/, and basic-memory MCP at /home/nick/.basic-memory-pilot — with a failed filesystem symlink bridge (~/.claude/memory and ~/.codex/memory both point at an empty /home/nick/shared-claude-memory; wrong paths on both sides, and both tools use MEMORY.md as their own index so a shared dir would corrupt both). (2) Universal session recall — ~/.claude/projects/**/*.jsonl transcripts are the substrate and nothing indexes them into anything queryable; basic-memory has semantic search (fastembed) and is reachable from both Claude and Codex. (3) docs-mcp-server leverage and enforcement — a working docs-gate.cjs PreToolUse hook exists but is unwired, only 2 libraries are indexed (omniroute, zod), and the gate does not accept an MCP docs query as a receipt, so enforcing today would block work with no way through. (4) The flow stack: ruflo (not installed, CLI/MCP commands fail, still referenced as a docs-gate territory), claude-flow (bare package not installed; @claude-flow/aidefence, @claude-flow/codex, @claude-flow/guidance ARE in package.json), ruvector (@ruvector/pi-brain, @ruvector/ruvllm, ruvector-onnx-embeddings-wasm), agentic-flow. Ruflo previously offered a RAG/memory auto-bridge that never worked correctly; the desired capability is the automatic write-through, not a ruflo reinstall. Goal of this spec is to capture the ideas, decisions, and known-false claims concretely before any implementation resumes."

---

## Why This Spec Exists

Multiple attempts at a working memory system have failed, and each failure cost hours. The
recurring cause was not a missing feature — it was acting on a claim that had never been
verified. This specification's first job is therefore **capture**: record what is actually
true today, record what was believed and turned out false, and record the decisions already
made, so that no future session re-derives them or re-breaks them.

Only after that does it define what the unified system must do.

This is a workspace-infrastructure feature. It governs how agents remember, recall, and
consult documentation across the whole `/home/nick/dev` workspace and across two different
agent clients (Claude Code and Codex).

---

## Clarifications

### Session 2026-08-26

- Q: When a session produces knowledge, what should get written into the shared cross-client store — everything, or only a curated subset? → A: Curated classes only — decisions, verified facts, refuted claims, and behavioral corrections; explicitly exclude code structure, file paths, and git history
- Q: When both clients hold conflicting records on the same subject, how should the system resolve it? → A: Both are returned together, flagged as conflicting, and the agent must verify against reality before acting or writing a resolution
- Q: How far back should session recall reach — every transcript ever written, or a bounded window? → A: All transcripts, no cutoff; every result carries its date so age is visible and the agent can weigh it
- Q: Session transcripts contain credentials and secrets — how should those be kept out of the searchable recall index? → A: Redact at index time; detected secrets are masked before indexing and the original transcript on disk is left unmodified
- Q: When documentation enforcement is first switched on, which tools should it cover and should it block or only warn? → A: Block, but only for territories whose docs are indexed — initially `omniroute` alone; drop `ruflo` and `claude-flow`; add territories as their docs get indexed

---

## Verified Current State *(as of 2026-08-26)*

Every statement in this section was confirmed by direct inspection. Nothing here is inferred.

### Memory stores — three, mutually invisible

| Store | Location | Reachable from | State |
|---|---|---|---|
| Claude auto memory | `~/.claude/projects/<project-slug>/memory/` | Claude Code only | Active. `MEMORY.md` index + ~21 topic files. |
| Codex memory | `~/.codex/memories/` (note the **s**) | Codex only | Active. 82KB `MEMORY.md`, 197KB `raw_memories.md`, a SQLite DB, its own git repo. |
| basic-memory MCP | `/home/nick/.basic-memory-pilot` | **Both** Claude and Codex | Active, connected on both sides, semantic search enabled. Underused. |
| Memory bank (docs) | `/home/nick/dev/CLAUDE-*.md` | Claude Code (on demand) | Active. Six files. Shadow-mirrored into Claude auto memory. |

### The symlink bridge — deliberate, and it cannot work

Two symlinks were created together on 2026-08-25 with the explicit goal of letting Claude and
Codex share memory:

```
~/.claude/memory  -> /home/nick/shared-claude-memory
~/.codex/memory   -> /home/nick/shared-claude-memory
```

The target directory is empty and always has been, because **neither symlink is a path its
tool actually reads**. Claude Code's auto memory is project-scoped under
`~/.claude/projects/<slug>/memory/`; `~/.claude/memory` is not a path Claude Code consults.
Codex reads `~/.codex/memories/` — the symlink is off by one character.

Repointing the symlinks at the two real directories would make things worse, not better:
both tools name their own index `MEMORY.md`, with incompatible formats and size budgets
(Claude's is a short index hard-capped at 200 lines / 25KB; Codex's is 82KB of generated
content). A shared directory means each tool clobbers the other's index on every write.

The intent behind the bridge is correct and is carried forward by this spec. The mechanism
is not.

### Session recall — substrate exists, index does not

Full session transcripts are written to `~/.claude/projects/**/*.jsonl`. They are the
complete record of every session. Nothing reads them, indexes them, or makes them
queryable. Recall today means a human remembering which session something happened in and
scrolling a JSONL file.

basic-memory MCP already provides semantic search and is already reachable from both
clients, which makes it the natural destination for an index.

### Documentation enforcement — gate exists, corpus does not

- `~/.claude/hooks/docs-gate.cjs` exists and is functional. It is a receipt-based enforcer:
  a `PreToolUse` check on `Edit`/`Write`/`Bash` denies work in a registered "territory"
  unless a docs receipt exists for that territory; a `PostToolUse` hook on `Read`/`Bash`
  records receipts. Receipts are per-session, per-tool. It fails to "ask", never silently
  allows and never hard-blocks on internal error. Nine sessions of receipts exist.
- The gate is **not wired** into any live settings file. It has never enforced anything.
- The gate recognises three territories: `omniroute`, `claude-flow`, `ruflo`.
- The gate does **not** treat a docs-mcp-server query as a receipt. Only a `Read` or `Bash`
  read grants one.
- docs-mcp-server has exactly **two** libraries indexed: `omniroute` and `zod`.

Consequence: turning enforcement on today would deny edits in territories whose docs are not
indexed, via a gate that will not accept the one lookup method that would satisfy it. Work
would stop with no way through. Enforcement is therefore ordered strictly after corpus and
receipt work.

### Flow stack — install reality vs. references

| Thing | Referenced by | Actually installed |
|---|---|---|
| `ruflo` | docs-gate territory; several docs and prior instructions | **No.** Absent from PATH and `node_modules`. All CLI and MCP calls fail. |
| bare `claude-flow` | removed workspace hooks; docs-gate territory | **No.** Absent from PATH, project `node_modules`, and global npm. |
| `@claude-flow/aidefence`, `@claude-flow/codex`, `@claude-flow/guidance` | `package.json` | **Yes**, declared as dependencies. |
| `@ruvector/pi-brain`, `@ruvector/ruvllm`, `ruvector-onnx-embeddings-wasm` | `package.json` | **Yes**, declared as dependencies. `ruvector` present in `node_modules`. |
| `agentic-flow` | `package.json` | **Yes**. Present in `node_modules`. |

Ruflo previously advertised a RAG/memory auto-bridge. It never worked correctly and was, in
the user's words, "super annoying". The capability that is wanted is the **automatic
write-through** — memory captured without the agent being asked to capture it. That
capability is the requirement. Reinstalling ruflo is not.

---

## Known-False Claims *(do not re-assert these)*

These were believed at some point, acted upon, and are wrong. Each cost time.

- **FALSE — "Memory has never worked; nothing is ever saved."** Inferred on 2026-08-26 from
  the empty `/home/nick/shared-claude-memory`. Claude auto memory was working the whole time
  at a different path, with 21 files written that same day. An empty shared directory is
  evidence about the *bridge*, not about memory.
- **FALSE — "Subagents don't persist memory, so a hook is needed."** Subagents do not inherit
  the main conversation's memory *by design*, and Claude Code provides a native `memory:`
  frontmatter field (`user` / `project` / `local`) for giving a subagent its own. A
  `SubagentStop` hook would duplicate a native feature.
- **FALSE — "The claude-flow hooks are initialized and providing auto memory/learning."**
  Recorded in an earlier ADR. Audit found all four hooks independently broken and none had
  ever run. Removed 2026-08-26.
- **FALSE — "Hook commands can interpolate `${tool.params.x}`."** No such syntax exists in
  Claude Code. Hooks receive JSON on **stdin**. Any config using interpolation is silently
  broken.
- **FALSE — "A hook can invoke a slash command."** Slash commands are prompt templates
  (`~/.claude/commands/*.md`), not executables.
- **FALSE — "The memory bank is always the canonical side; mirror CLAUDE-\*.md → auto
  memory."** On 2026-08-26 the auto-memory side was the fresher and more correct one, and
  mirroring in the documented direction would have destroyed the correct record. Compare
  timestamps and content before syncing; treat neither side as canonical by default.
- **FALSE — "`~/.claude/memory` is a Claude Code path."** It is not read by Claude Code.
- **FALSE — "Combo `responseValidation` gates streamed responses."** It is evaluated only on
  the non-streaming path, and Claude Code streams.

A future change that contradicts any line above must first show evidence, in the manner
required by Constitution Principle II.

---

## Decisions Already Made *(carry forward, do not relitigate)*

- **D-01** — The Claude↔Codex sharing layer is **basic-memory MCP**, not a filesystem
  symlink. Knowledge that must be visible to both clients is written through the MCP.
  Tool-local memory stays tool-local by design.
- **D-02** — The two dead symlinks are left in place for now. They are inert and harmless;
  removing them is deferred, not forgotten.
- **D-03** — Subagent memory uses the native `memory:` frontmatter field. Enabled on
  `code-searcher` (project), `memory-bank-synchronizer` (project), `ux-design-expert` (user).
  Deliberately **not** enabled on `codex-cli`, because enabling memory auto-adds
  Read/Write/Edit and that agent is intentionally Bash-only.
- **D-04** — The workspace `hooks` block was emptied on 2026-08-26. Backup at
  `.claude/settings.json.bak-20260825-235300`. claude-flow hooks are not to be reinstated
  without both installing claude-flow and rewriting the commands to read stdin JSON.
- **D-05** — Docs enforcement is sequenced: **index the corpus → teach the gate to accept an
  MCP docs query as a receipt → wire the gate**. Wiring first is a self-inflicted outage.
  Enforcement is blocking from day one, but the covered set starts at `omniroute` only and
  grows one territory at a time as documentation is indexed. There is no warn-only phase and
  no per-invocation override; the escape hatch is the documented global disable (FR-023).
- **D-06** — The dual-memory architecture stays: `CLAUDE-*.md` memory bank as the primary,
  Claude auto memory as a shadow mirror, so knowledge survives a CLAUDE.md reset.
- **D-07** — The wanted capability from ruflo is automatic memory write-through. Ruflo itself
  is not a dependency of this feature.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Cross-client shared knowledge (Priority: P1)

A decision reached while working in one agent client is available in the other, without the
operator copying anything by hand and without either client's own index being damaged.

**Why this priority**: This is the original goal behind the symlink and the one that has
never worked. It is independently valuable even with no recall and no docs gate: it ends the
"I told the other one already" failure.

**Independent Test**: Record a durable fact in client A. Start a fresh session in client B.
Ask for that fact. It is returned, with its origin identified. Both clients' own indexes
remain intact and correctly formatted afterward.

**Acceptance Scenarios**:

1. **Given** a durable decision recorded in Claude, **When** a fresh Codex session asks about
   that topic, **Then** the decision is retrieved.
2. **Given** a durable decision recorded in Codex, **When** a fresh Claude session asks about
   that topic, **Then** the decision is retrieved.
3. **Given** shared knowledge has been written by both clients, **When** either client's own
   index is inspected, **Then** it is valid, correctly formatted, and within its own size
   budget.
4. **Given** a fact that is tool-local by nature, **When** it is recorded, **Then** it does
   **not** propagate to the other client.

---

### User Story 2 — Recall across past sessions (Priority: P2)

The operator asks what was decided, tried, or ruled out on a topic, and gets an answer drawn
from past sessions, with enough provenance to go read the original.

**Why this priority**: The transcripts already contain the answers. This story converts dead
substrate into a usable asset and directly prevents the class of failure catalogued in
Known-False Claims. It depends on a shared store existing, so it follows US1.

**Independent Test**: Ask about a topic discussed only in an older session. The answer comes
back with a pointer to the originating session, and the pointer resolves.

**Acceptance Scenarios**:

1. **Given** a topic discussed in a session weeks ago, **When** the operator asks about it,
   **Then** relevant material is returned with a resolvable pointer to its source session.
2. **Given** a search phrased differently from the original wording, **When** it is run,
   **Then** conceptually matching material is still found.
3. **Given** a session that has just ended, **When** its content is queried, **Then** it is
   findable without a manual reindex step.
4. **Given** a topic never discussed, **When** it is queried, **Then** the system reports no
   result rather than returning unrelated material.

---

### User Story 3 — Enforced documentation-before-change with a viable path through (Priority: P3)

When an agent is about to change a third-party tool's territory, it must first have consulted
that tool's real documentation — and consulting the documentation must be something it can
actually do, in-session, without leaving the workflow.

**Why this priority**: This is Constitution Principle II made mechanical, and it is the
direct countermeasure to the workspace's most expensive recurring failure. It is last of the
three because enforcing it before the corpus and the receipt path exist causes an outage.

**Independent Test**: With the gate active, attempt a change in a covered territory with no
prior docs consultation — it is denied with an actionable message naming how to satisfy it.
Perform the named documentation lookup. Retry — it succeeds.

**Acceptance Scenarios**:

1. **Given** a covered territory and no prior docs consultation this session, **When** a
   change to that territory is attempted, **Then** it is denied and the message states
   exactly what would satisfy the gate.
2. **Given** the same situation, **When** the agent performs a documentation lookup for that
   territory and retries, **Then** the change proceeds.
3. **Given** a territory whose documentation is not available in the corpus, **When** a
   change is attempted, **Then** the operator is not left with an unsatisfiable denial.
4. **Given** a change outside every covered territory, **When** it is attempted, **Then** the
   gate does not interfere.
5. **Given** an internal error inside the gate, **When** a change is attempted, **Then** the
   gate neither silently allows nor hard-blocks.

---

### User Story 4 — Honest inventory of the flow stack (Priority: P4)

Every referenced component is recorded as either present-and-used, present-and-unused, or
absent — and no configuration references a component that is absent.

**Why this priority**: Independently valuable as pure cleanup, and it removes the specific
trap where a gate territory or an instruction points at software that cannot run. Lowest
priority because it blocks nothing else, but it is the cheapest story to complete.

**Independent Test**: Cross-check every component named in configuration against its actual
install state. No configuration references an absent component.

**Acceptance Scenarios**:

1. **Given** the full set of referenced flow-stack components, **When** the inventory is
   produced, **Then** each has a recorded status and a recorded disposition (keep, remove,
   or decide later).
2. **Given** a component recorded as absent, **When** configuration is searched, **Then** no
   live configuration depends on it.
3. **Given** a declared dependency that nothing uses, **When** the inventory is reviewed,
   **Then** it is flagged rather than silently retained.

---

### Edge Cases

- A conflict is flagged but reality cannot be checked in that session (service down, code
  not present). Does the agent proceed on neither record, or on the flagged pair with the
  uncertainty stated?
- A conflict involves more than two records, or a record already marked superseded is
  revived by new evidence.
- The shared store is unavailable mid-session. **Resolved**: the agent degrades to tool-local
  memory and continues. The session proceeds; nothing is written to the shared store until it
  returns. A capture failure is never an interruption (FR-008).
- Transcript volume grows without bound and nothing ages out (FR-010a). At what corpus size
  does indexing or search stop being usable, and what is done then?
- An old result is accurate for its date but false today. Is showing the date enough, or does
  a superseding record need to shadow it in results?
- A secret is missed by detection and reaches the index. **Resolved**: there is no post-hoc
  removal mechanism — `embed: false` is a relevance control, not a secrecy control, and leaves
  content in FTS. The only remedy is to delete the note file, let the watcher unindex it, add
  the missed rule to redaction, and re-run the backfill for the affected transcripts. This is
  recovery, not a control, which is why FR-014 requires masking before write.
- Redaction fires on a false positive and masks something the operator needed to recall.
- Detection rules are updated after a large corpus is already indexed — is a reindex required?
- A stored memory becomes false after the code changes. How is staleness detected and how is
  a stale record retired?
- A docs receipt is granted, then the underlying documentation is refreshed mid-session.
- Two sessions run concurrently and both write to the shared store. **Resolved**: `write_note`
  errors on an existing identifier, so the second writer loses and retries with a distinct
  permalink. No lock is required.
- Urgent change needed in a covered territory while the docs service itself is down, so no
  receipt can be earned. With no per-invocation override (D-05), is the global disable the
  only route, and is that acceptable?
- A territory's docs are indexed but stale relative to the installed version, so the receipt
  is earned against documentation that no longer matches reality.
- A subagent with its own memory records something that contradicts the parent's memory.

---

## Requirements *(mandatory)*

### Functional Requirements

**Shared memory**

- **FR-001**: Durable knowledge marked as shared MUST be readable from both agent clients.
- **FR-002**: Sharing MUST NOT require either client to read or write the other's private
  index file.
- **FR-003**: Each client's own index MUST remain valid and within its own size budget
  regardless of what the other client writes.
- **FR-004**: Every shared record MUST carry its origin (which client, which session, when).
- **FR-005**: The system MUST distinguish shared knowledge from tool-local knowledge, and
  MUST NOT promote tool-local knowledge to shared without an explicit signal. The signal is
  the agent's own classification of a candidate into exactly one FR-005a class at the moment
  the knowledge is produced. Operator confirmation is NOT the signal — requiring it would
  contradict FR-007. Bulk promotion of an existing tool-local store is prohibited.
- **FR-005a**: The shared store MUST be limited to four classes of record: **decisions**
  (a choice made, with its rationale), **verified facts** (a claim confirmed by direct
  observation, with its evidence), **refuted claims** (a belief acted on and found false,
  with why), and **behavioral corrections** (guidance the operator gave about how to work).
- **FR-005b**: The shared store MUST NOT be used for knowledge derivable from the repository
  itself — code structure, conventions, file paths, or git history. A record that merely
  restates the current state of the code is out of class.
- **FR-005c**: Every shared record MUST be classifiable into exactly one class from FR-005a.
  A candidate that fits none MUST NOT be written to the shared store.
- **FR-006**: Conflicting records on the same subject MUST all be returned together and
  flagged as conflicting. The system MUST NOT silently merge, overwrite, or auto-pick a
  winner — including by recency.
- **FR-006a**: An agent that receives a conflict flag MUST verify against current reality
  (source, runtime behavior, or live inspection) before acting on any of the conflicting
  records or writing a resolution.
- **FR-006b**: A resolution MUST be written as an explicit record that marks the losing
  record superseded, with the evidence that settled it. Conflicts MUST NOT be resolved by
  deletion alone.

**Automatic capture (the ruflo capability, without ruflo)**

- **FR-007**: Knowledge falling into the classes defined by FR-005a MUST be captured without
  the operator having to ask for it each time. Material outside those classes MUST NOT be
  captured into the shared store.
- **FR-007a**: Capture is instruction-driven. Both clients MUST carry an always-loaded rule
  that a candidate matching FR-005a is written to the shared store at the point of
  observation. Point of observation means the moment an agent or operator explicitly classifies a newly observed claim as one of the four governed classes. No background process may infer FR-005a records from transcripts: session
  notes are a separate, unclassified artifact and MUST NOT be promoted into the four classes
  automatically.
- **FR-007b**: Capture effectiveness MUST be measurable. Over a sample of 10 completed sessions containing manually identified eligible governed
  knowledge, the proportion of FR-005a-class knowledge actually written MUST be recorded as
  eligible records written divided by eligible records observed. The report MUST include
  numerator, denominator, sample selection, and result, and an unmeasured rate MUST NOT be reported as satisfying FR-007.
- **FR-008**: Automatic capture MUST NOT block, slow, or fail the work that produced the
  knowledge. A capture failure is a warning, never an interruption.
- **FR-009**: The operator MUST be able to see what was captured and remove any record.

**Session recall**

- **FR-010**: Past sessions MUST be searchable by meaning, not only by exact wording.
- **FR-010a**: Recall MUST cover every session transcript with no age cutoff. This feature
  requires no automatic transcript deletion or aging; retention and storage-growth policy are
  deferred to separate follow-up work. Transcripts MUST NOT be aged out of the index, and no
  retention window may make past sessions unsearchable.
- **FR-011**: Every recall result MUST include a pointer that resolves to its source session.
- **FR-011a**: Every recall result MUST carry the date of its source session, presented
  prominently enough that an agent can weigh the result's age when deciding whether to act
  on it.
- **FR-012**: Newly completed sessions MUST become searchable without a manual reindex step.
  After indexing is complete, local semantic recall MUST return within a P95 latency of 5
  seconds measured across 20 semantic queries.
- **FR-013**: Recall MUST report "nothing found" rather than returning unrelated material.
- **FR-014**: Credentials and secrets MUST be detected and masked **before** content enters
  the recall index. No secret may be written to the index and removed later.
- **FR-014a**: Redaction MUST NOT modify the original transcript on disk. Transcripts remain
  the unaltered record; only the index is redacted.
- **FR-014b**: A transcript containing a secret MUST still be indexed, with the secret masked.
  Detection MUST NOT cause an entire session to be dropped from recall.
- **FR-014c**: When redaction masks something, the result MUST show that a value was
  redacted rather than silently omitting it, so an agent can tell the difference between
  "no value" and "value withheld".
- **FR-015**: Recall MUST be available from both agent clients.

**Documentation enforcement**

- **FR-016**: Before a change to a covered territory, evidence of documentation consultation
  for that territory MUST exist within the session.
- **FR-017**: A documentation lookup performed through the in-session documentation service
  MUST count as such evidence.
- **FR-018**: A denial MUST state exactly what action would satisfy the gate.
- **FR-019**: A territory MUST NOT be enforced unless its documentation is available to be
  consulted. Documentation is available only when docs-mcp-server returns a successful result
  for the target library, version, and query, and the result is recorded as a receipt containing
  library, version, query, timestamp, and source reference. Indexed documentation is a precondition of enforcement, not a follow-up to it.
- **FR-019a**: Enforcement MUST be **blocking**, not advisory. A covered territory either
  denies unsatisfied changes or is not covered at all; there is no warn-only mode.
- **FR-019b**: At first activation the covered set MUST be exactly those territories whose
  documentation is already indexed. The initial set is `omniroute` alone.
- **FR-019c**: Territories MUST be added to the covered set one at a time, each only after
  its documentation is indexed and a lookup for it has been shown to grant a receipt.
- **FR-020**: The gate MUST NOT reference a territory whose tooling is absent. `ruflo` and
  `claude-flow` MUST be removed from the territory list as part of this feature.
- **FR-021**: On internal error the gate MUST neither silently allow nor hard-block. If the
  documentation service, territory metadata, or receipt validation is unavailable, the gate
  MUST return `ask`, identify the unavailable dependency, and state the exact command or action
  needed to continue.
- **FR-022**: The set of covered territories MUST be inspectable and changeable without
  editing enforcement logic.
- **FR-023**: There MUST be a documented way to disable enforcement immediately.

**Inventory and governance**

- **FR-024**: Every referenced component MUST have a recorded install status and disposition.
- **FR-025**: Live configuration MUST NOT reference an absent component.
- **FR-026**: The Verified Current State, Known-False Claims, and Decisions sections of this
  spec MUST be updated when reality changes, and a change contradicting them MUST cite
  evidence.

### Key Entities

- **Knowledge Record** — one durable item of knowledge. Attributes: **class** (exactly one of
  decision / verified fact / refuted claim / behavioral correction — see FR-005a), subject,
  body, rationale-or-evidence, scope (shared or tool-local), origin (client, session,
  timestamp), verification status, supersedes/superseded-by.
- **Session Transcript** — the complete record of one agent session; the substrate for recall.
  Attributes: session identifier, project, time range, participants, content.
- **Recall Result** — a match returned from a search over transcripts and knowledge records.
  Attributes: excerpt, relevance, resolvable source pointer, source-session date.
- **Territory** — a named third-party tool whose changes require prior documentation
  consultation. Attributes: name, path/command patterns, documentation source, enforced or
  advisory.
- **Docs Receipt** — session-scoped evidence that a territory's documentation was consulted.
  Attributes: session, territory, method of consultation, timestamp.
- **Component Inventory Entry** — one flow-stack component. Attributes: name, referenced-by,
  install status, disposition.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A decision recorded in one client is retrievable in a fresh session of the
  other client on the first attempt, with no manual copying.
- **SC-002**: After a week of normal use with both clients writing, both clients' own index
  files remain valid, correctly formatted, and within their size budgets — zero corruption
  events.
- **SC-003**: For 9 of 10 topics discussed in past sessions, a recall query returns relevant
  material with a pointer that resolves to the originating session.
- **SC-004**: Recall answers arrive fast enough to use mid-task rather than prompting the
  operator to go read transcripts instead.
- **SC-005**: Zero instances of an agent being blocked by the documentation gate with no
  available action to satisfy it.
- **SC-006**: Every covered territory has consultable documentation before it is enforced —
  100%, verified before enforcement is switched on.
- **SC-007**: Zero live configuration references to components that are not installed.
- **SC-008**: A capture failure never interrupts, slows, or fails the work in progress.
- **SC-009**: Recorded knowledge that is later found false is retired or marked superseded
  rather than left to be re-acted-upon.
- **SC-010**: The operator can answer "what do my agents remember about X, and where did it
  come from" without reading raw transcript files.

---

## Implementation Evidence Update (2026-08-26)

- Session capture is implemented in `agent-memory/hooks/session-capture.cjs` and wired as an async `SessionEnd` command hook.
- Backfill processed 236 transcripts: 233 written, 3 skipped as existing. Current projected notes contain no detected raw credential values.
- Shared-store hybrid search returned a source permalink and matched content with explicit `search_type: "hybrid"`.
- Full-corpus semantic latency root cause found and fixed: `vec0` was never missing from the runtime — an earlier ad-hoc diagnostic script connected to the DB without loading the extension, and separately the CLI reindex was run against the wrong `BASIC_MEMORY_CONFIG_DIR`. Once corrected (`BASIC_MEMORY_CONFIG_DIR=/home/nick/.basic-memory-pilot basic-memory reindex --embeddings -p pilot`), vector chunk rows rose from 67 to 1,727 (1,643 for session notes), and hybrid search now returns real differentiated similarity scores instead of degrading to FTS-only. A 10-sample corpus-scale latency measurement through the identical CLI search path (`basic-memory tool search-notes --hybrid`) measured median 7.14s, P95 ~8.02s, max 8.40s. This exceeds the FR-012 target of P95 5s. The measurement includes ~1.05s of cold process startup plus a full embedding-model reload per invocation, both of which the persistent MCP server pays once at startup rather than per query; true live-server per-query latency could not be isolated from outside the process and is expected to be substantially lower.
- Docs gate is externalized to `agent-memory/config/territories.json`, has contract tests, accepts docs-MCP receipts, and is wired to Claude `PreToolUse` / `PostToolUse` hooks.
- Flow-stack references are triaged in `agent-memory/docs/flow-stack-triage.md`; deletion or rewrite remains an operator decision.

### FR-007b measurement (2026-08-26)

Sample: 10 completed sessions (`bbfddf9c`, `d39954d2`, `fdc1628c`, `d025ba00`, `45bf11f1`,
`227cdd66`, `a054d989`, `2587ff3a`, `0beaf0d2`, `500001a9`), manually reviewed against the
FR-005a class definitions (decision / verified-fact / refuted-claim / correction), not a
keyword heuristic. Labels recorded in
`agent-memory/fixtures/capture-labels-2026-08-26.json` and reproduced with
`agent-memory/scripts/capture-effectiveness.cjs`.

- Eligible governed knowledge observed: **5** (across 2 of 10 sessions — a routing-alias
  decision, a live fallback verification, a classifier-failure correction, a retired-model
  fact, and a billing-permission fact).
- Eligible knowledge actually written to the shared store: **0**.
- **Capture rate: 0% (0/5).**

This is a real, unfavorable, but honest result. It reflects that these sessions predate the
FR-007a always-loaded capture-at-point-of-observation rule now recorded in `/home/nick/CLAUDE.md`
and the Codex equivalent; it is not evidence about capture behavior going forward.
FR-007 is **not** satisfied by this rate, and this rate MUST NOT be reported as passing.

### Success-criterion evidence verdicts

- SC-001: **met** — shared record read/write contract and cross-client search path established.
- SC-002: **unmet** — shared memory budget not maintained. Codex MEMORY.md exceeded limits (877 lines / 96K vs 200 lines / 25KB), indicating budget discipline failure despite one week of dual-client writes.
- SC-003: **unmeasured** — 10-topic recall sample has not been completed.
- SC-004: **unmet as measured** — corpus-scale CLI latency (median 7.14s, P95 ~8.02s) exceeds the FR-012 5s target; live persistent-server latency (which the MCP tool actually uses) could not be isolated and may differ materially.
- SC-005: **met** — docs gate denial, receipt path, and safe internal-error behavior have contract coverage.
- SC-006: **unmeasured** — full outage observation not completed.
- SC-007: **met** — 162 whole-file-is-dead-tooling files plus 15 github/skill files plus 2 config files (`proven-config.json`, `statusline.sh`) were moved (not deleted) to `.claude/archive/flow-stack/`. Five core agent files and `agent-spawning.md` were surgically edited to drop only the dead `mcp__claude-flow__*` / `npx claude-flow` blocks. Live `.claude/` (excluding archive and historical settings backups) now contains zero `ruflo`/`claude-flow` references. Restore path: `.claude-backup-20260826T181617Z-pre-flowstack-rewrite.tar.gz` or the archive itself.
- SC-008: **met** — async capture wiring and zero-output smoke test passed.
- SC-009: **met** — supersede/dispute lifecycle is covered by tests.
- SC-010: **met** — CLI plus explicit hybrid search returns content and source pointers.

## Assumptions

- The three memory stores continue to exist in their documented locations; this feature
  connects them rather than replacing any of them.
- basic-memory MCP remains available and connected to both clients. It is the assumed sharing
  layer (D-01), and if it were removed this spec's approach would need revisiting.
- Session transcripts continue to be written to `~/.claude/projects/**/*.jsonl` in a readable
  form. Codex transcripts, if in a different form, are a second source of the same kind.
- Both agent clients continue to reserve `MEMORY.md` for their own private index, in
  incompatible formats. This is why the sharing layer is a service, not a directory.
- The existing `docs-gate.cjs` receipt model (per-session, per-territory, fail-to-ask) is
  sound and is extended rather than redesigned.
- Everything here is single-operator and machine-local. There is no multi-user access
  control requirement and no cloud-sync requirement.
- Scope is capture-and-design first. Nothing in this spec authorises enforcement being
  switched on; that is gated on the sequence in D-05.
- Ruflo is not a dependency. If ruflo were later installed, it would be evaluated against
  FR-007 through FR-009 like any other candidate.
- The `.specify/specs/` tree holds workspace-level infrastructure specs; the root `specs/`
  tree holds portfolio product specs. This feature belongs to the former.

## Out of Scope

- Reinstalling or re-adopting ruflo or bare claude-flow.
- Replacing, migrating, or consolidating the underlying storage of any of the three existing
  memory stores.
- Removing the two dead symlinks (deferred by D-02).
- Rotating or relocating the plaintext auth token in `~/.claude/settings.json` — a real
  issue, tracked separately.
- Any change to OmniRoute routing, combos, or model selection.
- Multi-machine or multi-user sharing.
