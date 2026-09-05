# Phase 0 Research: Unified Agent Memory, Session Recall, and Documentation Enforcement

**Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)

All findings below were obtained by reading source, schemas, live tool output, or official
documentation — per Rule #1 and Constitution Principle II. Every claim carries its evidence.
Anything not verified is marked **UNVERIFIED** and is not relied upon by the plan.

---

## R1. Prior art — this decision was already made and benchmarked

**Decision**: Adopt the existing 2026-08-19 decision rather than re-deciding. It is recorded
in basic-memory at `pilot/decisions/searchable-memory-selection`.

**Findings**:

- Basic Memory was already selected as "the single permanent searchable-memory layer for
  Context Hydration", with Claude Code native auto-memory retained for stable user/workspace
  preferences. This is spec decision D-01, already made.
- **Conflict handling was already benchmarked**: "Multi-note retrieval selected active
  `cobalt` over superseded `amber`, reported conflicting Meridian values `42` and `57` as
  **disputed**, and rejected unrelated `tin-lantern` as a negative control." This validates
  the clarify answer to Q2 (surface both, flagged) with a passing test.
- **Warm hybrid retrieval measured at ~0.106 s.** This supplies the number for SC-004.
- The note already mandates record shape: "Claims require provenance, observation time when
  known, confidence, and active/superseded/disputed status." Adopted directly into the data
  model.
- "Search mode should be explicit for benchmarked or precision-sensitive retrieval."

**Alternatives already considered and rejected (do not revisit without new evidence)**:

- *Claude-mem automatic capture* — retired reversibly. "Claude-mem 13.15.2 captured prompts
  but produced zero observations; its isolated provider process could not inherit interactive
  OAuth." **The automatic write-through capability has already been attempted once and failed
  on authentication, not on concept.** This directly informs R4: the capture path must not
  depend on a separate authenticated process.
- *TencentDB-Agent-Memory Proxy/Core/Hub* — rejected; dependency and operational surface
  exceeded the retrieval requirement.

---

## R2. basic-memory MCP — capabilities and hard limits

**Decision**: Use the existing `pilot` project as the shared layer. Convert transcripts to
markdown and let the running filesystem watcher index them; do not attempt raw `.jsonl`
ingest.

**Findings**:

- **Same server, same project, both clients — confirmed.** `~/.codex/config.toml:113-119`
  and `~/.claude.json:962-978` both run `uvx --from basic-memory==0.22.1 ... --project pilot`
  with `BASIC_MEMORY_CONFIG_DIR=/home/nick/.basic-memory-pilot`. Only difference is Claude
  declaring `"type": "stdio"` explicitly. D-01 is mechanically sound.
- **Search is genuinely hybrid and enabled.** FTS5 `search_index` (unicode61) plus
  `search_vector_embeddings` as `vec0 float[384]`. Model
  `FastEmbedEmbeddingProvider:bge-small-en-v1.5:384`. `_default_search_type()`
  (`mcp/tools/search.py:42-55`) returns `"hybrid"` because `semantic_search_enabled: true`.
  Config tuning: `semantic_vector_k: 100`, `semantic_min_similarity: 0.55`.
  Caveat: the service layer falls back to FTS when no mode is supplied
  (`services/search_service.py:201`); the MCP layer is what supplies `hybrid`. Precision-
  sensitive queries should pass `search_type` explicitly (also per R1).
- **A filesystem watcher is running and is a supported ingest path.** `watch-status.json`,
  pid 2339371, `sync_changes: true`, `awatch(debounce=sync_delay)`
  (`watch_service.py:142-144`), `sync_delay: 1000` → **~1 s to reindex**.
- **BLOCKER — non-markdown files are indexed as metadata only.** `sync_service.py:958-964`
  branches on `is_markdown`; non-markdown takes the `note_type="file"` path (`:1200-1212`)
  storing only title/checksum/size/mime. **No content extraction, no FTS rows, no
  embeddings.** Dropping `.jsonl` in yields searchable filenames and nothing else.
- **BLOCKER — hidden paths are filtered.** `watch_service.py:284-329` skips any path part
  starting with `.` *relative to the project root*. A project root under a hidden parent is
  explicitly supported (code comments name `~/.claude`), so the notes root itself is fine;
  dot-named subfolders inside it are not.
- **No native importer matches Claude Code transcripts.**
  `importers/claude_conversations_importer.py` targets the **claude.ai web export** shape
  (`chat_messages[]`, `sender`, `text`, `attachments`), not `~/.claude/projects/**/*.jsonl`.
  `Importer` (`importers/base.py`) is the extension point if a native one is ever wanted.
- `write_note` **errors on an existing identifier by default** (`write_note.py:59`,
  resolution order at `:201-205`); config sets `write_note_overwrite_default: false`. No
  versioning — overwrite replaces.
- Permalink = `{project}/{folder}/{kebab-title}` because `permalinks_include_project: true`.
  Unique per project (`uix_entity_permalink_project`).
- `note_type` is free text, stored in frontmatter and indexed (`ix_note_type`).
- **No built-in supersede or contradiction concept.** A `relation` table exists
  (`from_id`, `to_id`, `to_name`, `relation_type`), `relation_type` is free and indexed, and
  `to_name` holds unresolved forward references — so a note can link to one that does not
  exist yet. Modelling supersession is ours to do.
- `edit_note` operations: `append`, `prepend`, `find_replace`, `replace_section`
  (`edit_note.py:189-219`). `append`/`prepend` auto-create.
- **BLOCKER — `embed: false` excludes a note from semantic indexing only**
  (`search_service.py:741-763`); it remains in FTS. There is no built-in mechanism to hide
  content from search. This is why redaction must happen before write.
- Store is essentially empty today: 6 entities, 32 observations, 6 relations, 67 vector
  chunks, 48 FTS rows. `memory.db` 2.0 MB. The shared layer exists and is unused.
- **UNVERIFIED**: search latency at corpus scale (only the 0.106 s warm figure from R1's
  prior benchmark, taken against a near-empty store); documented note-count/size limits.

**Alternatives considered**:

- *Drop `.jsonl` into the watched notes dir* — rejected, metadata-only indexing.
- *Write a native basic-memory importer* — deferred; larger surface than converting to
  markdown, and the conversion is needed for redaction anyway.
- *Repoint the `~/.claude/memory` and `~/.codex/memory` symlinks at the real dirs* — rejected
  in the spec (both tools use `MEMORY.md` with incompatible formats).

---

## R3. Session transcripts — format and scale

**Decision**: Index a curated projection of each transcript — compaction summaries, human
prompts, and assistant prose — not raw lines.

**Findings**:

- **Line schema**: one JSON object per line. Conversation records carry `uuid`, `parentUuid`
  (threading is a linked list), `sessionId`, `timestamp` (ISO-8601 Z), `cwd`, `gitBranch`,
  `version`, `userType`, `isSidechain`, `entrypoint`. Payload is nested at `.message` with
  `.message.role` and `.message.content`. **Roles are not top-level.** Assistant records add
  `requestId` and `.message.model`; content is an array of typed blocks (`text`, `tool_use`,
  `thinking`).
- **Session identity is free**: path is `<project-slug>/<sessionId>.jsonl` — the filename
  **is** the sessionId. Slug is cwd with `/` → `-` (`/home/nick/dev` → `-home-nick-dev`).
  Session id → path is a string join; no index needed. Satisfies FR-011 cheaply.
- **Subagent transcripts live in a sibling tree**, not inline:
  `<slug>/<sessionId>/subagents/agent-<id>.jsonl` plus `agent-<id>.meta.json`. `isSidechain`
  was true 0 times in the sample — do not expect subagent turns in the parent file.
- **Tool results** are `type:"user"` records carrying a top-level `toolUseResult` field.
- **Noise ratio, measured on an 11.8 MB file**: `toolUseResult` 4.97 MB (42%), `attachment`
  records 2.38 MB (20%), `tool_use` blocks 1.96 MB (17%), assistant prose 0.52 MB (4.4%),
  **actual human prompts 169 KB (1.4%, 91 prompts)**. ~79% is tool traffic.
- **Corpus today**: 8 project dirs · **233** `.jsonl` files · **194 MiB** · largest 13.8 MB ·
  range 2026-08-18 → 2026-08-26 (8 days). ≈24 MB/day, ≈8.7 GB/year at the current rate.
  This is the number that makes FR-010a (no cutoff) a real engineering constraint rather
  than a free choice.
- **Compaction summaries exist and are the cheap indexing unit.** Records with
  `isCompactSummary: true` (`type:"user"`). One 11.8 MB file held 5 of them totalling 238 KB
  (13–31 KB each) — prose summaries of everything preceding. **44 of 233 files** contain at
  least one. Indexing summaries + human prompts + assistant prose is ≈8% of corpus bytes and
  drops ≈79% of the noise.
- **There is no `type:"summary"` record** — 0 hits across 60 files. The field is
  `isCompactSummary` on a user record.
- **Secrets are present, not hypothetical.** Clean on `sk-ant-*`, `ghp_*`, `gho_*`, `AKIA*`,
  `Bearer <…>`, PEM blocks, JWTs (0 hits each). But `ANTHROPIC_AUTH_TOKEN` appears **641
  times across 32 files**, and **152 of those are followed by an actual value across 25
  files** — 115 at length 35, consistent with a real key. FR-014 is load-bearing.

**Alternatives considered**:

- *Index raw lines* — rejected; 79% noise, and 194 MiB growing 24 MB/day.
- *Index only compaction summaries* — rejected alone; only 44 of 233 files have one, so 189
  sessions would be invisible. Summaries are one of three inputs, not the only one.

---

## R4. Hook mechanics — how capture and enforcement actually attach

**Decision**: Capture via a `SessionEnd` **command** hook with `async: true` that writes
redacted markdown into the watched notes directory. Enforcement stays a `PreToolUse` /
`PostToolUse` command-hook pair.

**Findings** (source: <https://code.claude.com/docs/en/hooks.md>):

- **31 valid hook events**, and `SessionEnd` is among them ("When a session terminates").
  A prior intermediate report listing 18 events was incomplete; corrected here.
  Full list: `SessionStart`, `Setup`, `UserPromptSubmit`, `UserPromptExpansion`,
  `PreToolUse`, `PermissionRequest`, `PermissionDenied`, `PostToolUse`, `PostToolUseFailure`,
  `PostToolBatch`, `Notification`, `MessageDisplay`, `SubagentStart`, `SubagentStop`,
  `TaskCreated`, `TaskCompleted`, `Stop`, `StopFailure`, `TeammateIdle`, `InstructionsLoaded`,
  `ConfigChange`, `CwdChanged`, `DirectoryAdded`, `FileChanged`, `WorktreeCreate`,
  `WorktreeRemove`, `PreCompact`, `PostCompact`, `Elicitation`, `ElicitationResult`,
  `SessionEnd`.
- **Common stdin fields on every event**: `session_id`, `prompt_id`, `transcript_path`,
  `cwd`, `hook_event_name` (plus `permission_mode` / `effort` where documented, and
  `agent_id` / `agent_type` under subagents). **`transcript_path` is handed to the hook
  directly** — the indexer needs no path derivation.
- **`SessionEnd` hooks share a 1.5-second budget**, raised to match a longer explicit
  `timeout` up to **60 seconds**. `SessionEnd` cannot block (exit 2 only surfaces stderr).
  Its matcher filters the termination reason: `clear`, `resume`, `logout`,
  `prompt_input_exit`, `other`.
- **`async: true` exists on command hooks** — "runs in the background without blocking."
  `asyncRewake: true` additionally wakes Claude on exit code 2, surfacing stderr as a system
  reminder. **`async: true` is what satisfies FR-008**: a fire-and-forget hook cannot block
  or slow the work, and it sidesteps the 1.5 s budget entirely.
- **MCP tools appear as regular tools in tool events.** Confirmed for `PreToolUse`,
  `PostToolUse`, `PostToolUseFailure`, `PermissionRequest`, `PermissionDenied`. Naming is
  `mcp__<server>__<tool>`. **A matcher must append `.*`** — `mcp__docs-mcp-server` alone is
  compared as an exact string and matches nothing; `mcp__docs-mcp-server__.*` works. This is
  the mechanism that makes an MCP docs query observable (FR-017).
- **An `mcp_tool` hook handler type exists** — fields `server` (must already be connected),
  `tool`, and optional `input` supporting `${path}` substitution from the hook payload.
  Available on every event once servers are connected; `SessionStart`/`Setup` fire before
  connection and should expect a "not connected" error. A timed-out `mcp_tool` hook renders
  no decision.
- **`memory:`** accepts exactly `user` | `project` | `local`, mapping to
  `~/.claude/agent-memory/<agent>/`, `.claude/agent-memory/<agent>/`,
  `.claude/agent-memory-local/<agent>/`. `project` is the documented recommended default.
  Read/Write/Edit are auto-enabled "so the subagent can manage its memory files." Gated
  behind auto memory; injected context capped at the first 200 lines or 25 KB of `MEMORY.md`.
- **UNVERIFIED**: the exact field name carrying the `SessionEnd` reason (the per-event schema
  section was truncated); the full `hookSpecificOutput` schema per event.

**Alternatives considered**:

- *`mcp_tool` hook on `SessionEnd` writing straight to basic-memory* — rejected as the
  primary path. It cannot redact (FR-014 requires transformation before write), and
  `SessionEnd`'s 1.5 s shared budget is hostile to a synchronous MCP round-trip. Kept as a
  future option for small, already-clean records.
- *A long-running indexer daemon* — rejected. This is exactly the shape that failed as
  Claude-mem (R1): a separate process that could not inherit interactive credentials. An
  `async` command hook runs as the user, in the user's environment, and needs no auth.
- *`Stop` instead of `SessionEnd`* — deferred; `SessionEnd` is the documented terminate
  event and its reason matcher lets `clear` and `resume` be handled distinctly.

---

## R5. docs-gate.cjs — actual enforcement surface

**Decision**: Externalise the territory list, shrink the enforced set to an allowlist, and add
one branch that accepts an MCP docs query as a receipt.

**Findings** (source: `/home/nick/.claude/hooks/docs-gate.cjs`):

- **Control flow**: reads stdin, uses exactly three fields — `session_id`, `tool_name`,
  `tool_input` (L127–129). `pass()` is a bare `exit(0)` with no stdout (L102).
  `deny()`/`ask()` emit `{hookSpecificOutput:{hookEventName:"PreToolUse",
  permissionDecision:"deny"|"ask", permissionDecisionReason:reason}}` and **also exit 0**
  (L95–101) — the decision rides in stdout JSON, never in the exit code.
- **`check` mode** (L148–164): for each target with `write:true`, resolve `ownerOf(p)`; if
  owned and no receipt exists, `deny` with `docHints()`.
- **`receipt` mode** (L131–146): for each non-write target, write a receipt for the owning
  tool. Plus a Bash-only branch (L138–143): if the command does not match `WRITE_RE`, the
  regex `([a-z0-9@/._-]+)\s+--help` grants a receipt named `basename($1)`.
- **CRITICAL — the territory list is inline** at L21–25 as a hardcoded `const`, not loaded
  from a file. **FR-022 is not satisfied today**; changing territories means editing
  enforcement logic.
- **CRITICAL — the real enforcement surface is far larger than three territories.** `ownerOf`
  (L32–40) falls through to `PKG_RE` (L27): **any `**/node_modules/<pkg>` path is a territory
  owned by `<pkg>`.** So the gate covers three directories *plus every installed package*.
  The spec's premise understated this, and it is the single largest outage risk in wiring the
  gate — the docs corpus holds 2 libraries against a territory set numbering in the hundreds.
- **CRITICAL — the `claude-flow` pattern is unanchored**: `(^|\/)\.claude-flow(\/|$)` matches
  **any** path segment. `/home/nick/dev/.specify/.claude-flow` exists on disk. Writing there
  demands a `claude-flow` receipt; claude-flow is not installed, so `docHints` degrades to
  `` `claude-flow --help` `` (L85), which fails. **An unsatisfiable denial, reachable today.**
  This is concrete proof of FR-020's necessity.
- **Receipts**: `~/.claude/.docs-receipts/<session_id||'nosession'>/<tool with [/@]→_>`
  (L42–44). Content is a ≤500-char note; **existence is the only test** (L45–47) — content is
  never parsed. **No expiry, no TTL.** 9 session dirs persist.
- **No MCP tool name is recognised anywhere.** `tool_name` is consulted only to decide Bash
  parsing (L108). The minimal fix is a third branch in `receipt` mode.
- **Fail-to-ask** has three triggers, all → `ask`: empty stdin (L122), unparseable JSON
  (L125), any uncaught throw in `main()` (L168). FR-021 already holds.

---

## R6. docs-mcp-server — and why the gate must observe, not verify

**Decision**: Grant the receipt from the **`PostToolUse` hook observing the tool call**, keyed
on `tool_input.library`. Do not attempt to verify against the server's store.

**Findings**:

- `list_libraries` returns exactly `omniroute` and `zod`. **Confirmed.** Output is a bare
  bullet list with no versions or document counts.
- `scrape_docs` requires `url` + `library`; optional `version`, `maxDepth` (3), `maxPages`
  (1000), `scope` (`subpages|hostname|domain`), `followRedirects`, `preserveHashes`. It is
  job-based — `list_jobs` reports queued/running/completed/failed/cancelling/cancelled.
  **UNVERIFIED**: typical indexing duration (no scrape was run).
- `search_docs(library, query, [version], [limit=5])`. The result is **plain prose text** —
  `Result N: <url>` plus markdown. **No structured library/version/doc-id field.** The
  *input* carries `library`; the output does not. Therefore any receipt must be derived from
  the tool **input**, not its result.
- **The local `~/.local/share/docs-mcp-server/documents.db` is a decoy** — it exists and
  every table has 0 rows. The server runs in **Docker**
  (`ghcr.io/arabold/docs-mcp-server:latest`, configured as `{type:"sse",
  url:"http://localhost:6280/sse"}`); the real index is the named volume `docs-mcp-data` at
  `/var/lib/docker/volumes/docs-mcp-data/_data/documents.db` (`DOCS_MCP_STORE_PATH=/data`).
- **All three store-based verification routes fail**:
  1. *Read the server store* — the volume path is root-owned; a user-level read is denied. A
     hook running as `nick` cannot read it.
  2. *Even with access it could not work* — the schema is `_schema_migrations, libraries,
     versions, pages, documents, metadata, documents_fts*, documents_vec*`. There is **no
     query, search, audit, or log table.** The DB stores the corpus and never records that a
     search occurred. This rules the approach out on principle, not merely on permissions.
  3. *HTTP API* — `GET /api` returns `{"error":"Not Found"}`. No query-log endpoint found.
- **Therefore observation is the only viable mechanism**, and it is sufficient: a
  `PostToolUse` hook matching `mcp__docs-mcp-server__.*` receives `tool_input.library`
  directly. It needs no MCP access, no container access, and no result parsing. Confirmed
  viable by R4 (MCP tools do fire tool events and are matchable with a `.*` suffix).

---

## R7. Flow-stack inventory

**Decision**: Remove `ruflo` and bare `claude-flow` from all live configuration. Retain the
scoped `@claude-flow/*`, `@ruvector/*`, and `agentic-flow` packages, which are real.

**Findings** (all by direct inspection):

| Component | Declared in `package.json` | In `node_modules` | Binary in `.bin` |
|---|---|---|---|
| `ruflo` | No | **No** | No |
| bare `claude-flow` | No | **No** | No |
| `@claude-flow/codex` | Yes (`^3.0.1`) | Yes | `claude-flow-codex`, `claude-flow-hooks` |
| `@claude-flow/aidefence`, `@claude-flow/guidance` | Previously recorded as declared | **UNVERIFIED** this pass — only `@claude-flow/codex` matched the dependency scan | — |
| `agentic-flow` | Yes | Yes | `agentic-flow`, `agentic-flow-repair` |
| `ruvector` | **No** — arrives transitively via `agentic-flow` | Yes | `ruvector`, `ruvllm` |
| `@ruvector/pi-brain`, `@ruvector/sona`, `@ruvector/graph-transformer` | — | Yes | — |

- **183 live (non-backup) files reference `ruflo` or `claude-flow`.** Breakdown:
  `.claude/commands/**` (~130 slash commands), `.claude/skills/*/SKILL.md` (20),
  `.claude/agents/core/*` and `.claude/agents/swarm/*` (8), `.claude/helpers/*` (30+, incl.
  `ruflo-hook.cjs`), `.claude/proven-config.json`, `.claude/statusline.sh`. Each instructs an
  agent to invoke a binary that does not exist.
- Nothing in any live `settings.json` invokes `.claude/helpers/**` — those scripts are
  orphaned, reachable only if a command or skill body tells an agent to run them.
- `/home/nick/dev/.specify/.claude-flow/` exists (`neural/stats.json`, `policy/state.json`)
  and is matched by the gate's unanchored `claude-flow` pattern (R5).

**This is the largest work item in the feature.** FR-025 was scoped as cleanup; it is not.

---

## Open items carried into Phase 1

| # | Item | Disposition |
|---|---|---|
| O-1 | Search latency at 194 MiB-plus corpus scale | **Unresolved**: active SQLite process reports `no such module: vec0`; projection-only P95 11.43 ms is not end-to-end recall evidence |
| O-2 | `SessionEnd` reason field name | Confirm from the per-event schema before writing the matcher |
| O-3 | `@claude-flow/aidefence`, `@claude-flow/guidance` declaration status | Re-verify during the inventory task |
| O-4 | docs-mcp-server indexing duration per library | Measure on the first real scrape |
| O-5 | Disposition of the 183 referencing files | Requires an operator decision on delete vs. rewrite; surfaced in plan Complexity Tracking |
