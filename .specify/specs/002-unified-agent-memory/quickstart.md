# Quickstart: validating unified agent memory

**Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Runnable scenarios proving the feature end to end. Each maps to a user story and a success
criterion. Run in order — later scenarios depend on earlier state.

Details are not repeated here; see [`data-model.md`](./data-model.md) and
[`contracts/`](./contracts/).

---

## Prerequisites

Verify before starting. **All of these exist today** — this feature installs nothing.

```bash
# 1. basic-memory MCP is configured identically for both clients
grep -A6 'basic-memory' ~/.codex/config.toml
python3 -c "import json;print(json.load(open('$HOME/.claude.json'))['mcpServers']['basic-memory-pilot'])"

# 2. The filesystem watcher is running
cat /home/nick/.basic-memory-pilot/watch-status.json

# 3. docs-mcp-server is up
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:6280/sse

# 4. The transcript corpus
ls -1 ~/.claude/projects/*/*.jsonl | wc -l    # expect ~233 and rising
du -sh ~/.claude/projects                     # expect ~194 MiB and rising
```

Expected: both clients name project `pilot` with
`BASIC_MEMORY_CONFIG_DIR=/home/nick/.basic-memory-pilot`; watcher `running: true`;
docs endpoint reachable.

**Stop if any check fails.** Every scenario below assumes this baseline.

### Baseline snapshot

```bash
sqlite3 /home/nick/.basic-memory-pilot/memory.db \
  "SELECT (SELECT count(*) FROM entity), (SELECT count(*) FROM search_index);"
```

Record the numbers — several scenarios assert on the delta. Today: 6 entities, 48 FTS rows.

---

## Setup

```bash
cd /home/nick/dev/agent-memory
node --test tests/            # unit + contract tests, no dependencies
```

All tests must pass before wiring anything into `~/.claude/settings.json`. The gate is
blocking (FR-019a); a wrong gate stops work.

---

## Scenario 1 — Cross-client shared knowledge (P1, SC-001)

**Proves**: a decision recorded in one client is retrievable from the other.

1. In **Claude Code**, write a knowledge note per
   [`knowledge-note.schema.md`](./contracts/knowledge-note.schema.md):
   `type: decision`, `status: active`, non-empty `rationale` and `provenance`.
2. Wait ~2 s (watcher debounce is 1000 ms).
3. In **Codex**, `search_notes` for a distinctive phrase from the body.

**Expected**: the note is returned with frontmatter intact — same permalink, same `status`.

**Failure to watch for**: a hit whose body is empty and which carries only title/checksum/size
means the file was not written as markdown. Non-markdown is indexed as metadata only.

---

## Scenario 2 — Conflict surfaced, not resolved (P1, SC-009, FR-006)

**Proves**: contradictory records are both returned and flagged; nothing is silently merged,
overwritten, or auto-picked — including by recency.

1. Write note A: a claim with a specific value, `status: active`.
2. Write note B: the **same subject, different value**, with a `contradicts` relation to A.
3. Mark both `status: disputed`.
4. Search the subject from **either** client.

**Expected**: **both** notes returned, both flagged `disputed`. Neither deleted. The later
write did not win.

This exact behaviour was already benchmarked on 2026-08-19 — conflicting Meridian values `42`
and `57` reported as disputed, active `cobalt` chosen over superseded `amber`, unrelated
`tin-lantern` correctly rejected as a negative control. Scenario 2 reproduces a passing test,
so a failure here is a regression against known-good behaviour.

**Also verify retention is mechanical**: attempting `write_note` at A's existing identifier
must **error**, not overwrite (`write_note_overwrite_default: false`).

---

## Scenario 3 — Capture never blocks (P2, SC-008, FR-008)

**Proves**: capture adds no latency to the blocking path.

1. Wire the `SessionEnd` hook per
   [`session-capture-hook.md`](./contracts/session-capture-hook.md) — `async: true`, **no
   matcher**.
2. Start a session, issue a few prompts, exit.
3. Time the exit. Then confirm the note landed.

```bash
ls -lt /home/nick/.basic-memory-pilot/notes/sessions/ | head -5
```

**Expected**: exit is not perceptibly delayed, and the note appears shortly afterwards.
`async: true` runs in the background without blocking, so the 1.5 s shared `SessionEnd` budget
is never the constraint.

**Failure to watch for**: a perceptible pause at exit means `async` was omitted or misplaced.
It is a **command-hook-only** field, a sibling of `type` and `command` in the inner `hooks`
array.

---

## Scenario 4 — No secret reaches the index (P2, FR-014, FR-014c) ⚠️ load-bearing

**Proves**: redaction happens before write, and fails closed.

This is the scenario that must not be skipped. Secrets in the corpus are confirmed, not
hypothetical: `ANTHROPIC_AUTH_TOKEN` appears 641 times across 32 files, **152 of those
followed by a real value across 25 files**.

```bash
# Against a transcript known to contain a token value:
node hooks/session-capture.cjs < fixtures/sessionend-with-token.json

# The rendered note must contain the mask and NOT the value:
grep -c '⟨redacted:' /home/nick/.basic-memory-pilot/notes/sessions/<new-note>.md
```

Then assert the value is absent from **the index**, not just the file:

```bash
sqlite3 /home/nick/.basic-memory-pilot/memory.db \
  "SELECT count(*) FROM search_index WHERE content LIKE '%<first 8 chars of value>%';"
```

**Expected**: mask count > 0; index count **0**.

**Fail-closed check**: feed a projection that still matches a rule after redaction. Expected —
nothing written, non-zero exit.

There is **no recovery path** if this fails. `embed: false` excludes semantic indexing only
and leaves content fully present in FTS; there is no built-in way to hide indexed content.
Skipping one session note is recoverable; an indexed credential is not.

---

## Scenario 5 — Recall across past sessions (P2, SC-003, SC-004, FR-010a)

**Proves**: knowledge from an old session is recallable, with no age cutoff.

1. Backfill the corpus through the projection (all 233 transcripts).
2. From **Codex**, search for a distinctive phrase you know appeared in a session from the
   oldest day present (2026-08-18).
3. Time the query.

**Expected**: the session note is returned, and its `provenance` gives the `session_id`. Since
the transcript path is `<slug>/<sessionId>.jsonl`, that id resolves back to the original file
by string join — no index needed (FR-011).

**On latency**: semantic vector indexing is currently unavailable in the active SQLite process
(`no such module: vec0`), so full-corpus hybrid recall latency is **unmeasured**. A local
projection benchmark across 20 transcript samples measured P95 **11.43 ms**, but this is not
an end-to-end recall measurement and does not satisfy SC-004.

**Pass `search_type` explicitly.** The MCP layer defaults to `hybrid`, but the service layer
falls back to FTS when no mode is supplied.

---

## Scenario 6 — Docs gate blocks, and the MCP query unblocks (P3, SC-005, FR-017)

**Proves**: enforcement is real, and there is a way through it.

Run **before** wiring, by piping payloads directly:

```bash
# 6a. Write into an enforced territory with no receipt → deny
echo '{"session_id":"qs","tool_name":"Write","tool_input":{"file_path":"/home/nick/dev/omniroute/x.ts"}}' \
  | node hooks/docs-gate.cjs check

# 6b. Observe an MCP docs query → receipt written
echo '{"session_id":"qs","tool_name":"mcp__docs-mcp-server__search_docs","tool_input":{"library":"omniroute","query":"routing"}}' \
  | node hooks/docs-gate.cjs receipt
ls ~/.claude/.docs-receipts/qs/

# 6c. Repeat 6a → now passes
```

**Expected**: 6a emits `permissionDecision: "deny"` **and exits 0** — the decision rides in
stdout JSON, never in the exit code. 6b writes a receipt named `omniroute`. 6c emits nothing.

The receipt is keyed on `tool_input.library` — the **input**, not the result. `search_docs`
returns plain prose with no structured library field.

Store-based verification was ruled out on principle: the docs-mcp-server schema has **no
query, search, audit, or log table**, so the DB never records that a search happened. The
root-owned Docker volume is a second, independent blocker. Observation is the only mechanism.

**Settings matcher must be `mcp__docs-mcp-server__.*`** — the trailing `.*` is required. A
matcher without it is compared as an exact string and matches no tool. Verify after wiring
that 6b fires for real, not just when piped by hand.

---

## Scenario 7 — The gate does not cause an outage (P3, SC-005, SC-006, FR-019b) ⚠️ load-bearing

**Proves**: blocking enforcement does not block everything.

This is the outage scenario. The existing gate's `PKG_RE` fall-through makes **any**
`**/node_modules/<pkg>` path a territory owned by `<pkg>` — hundreds of territories against
**two** indexed libraries.

```bash
# 7a. Unlisted package → must PASS (proves PKG_RE is constrained)
echo '{"session_id":"qs","tool_name":"Write","tool_input":{"file_path":"/home/nick/dev/node_modules/lodash/x.js"}}' \
  | node hooks/docs-gate.cjs check

# 7b. Indexed but not enforced (zod) → must PASS
echo '{"session_id":"qs","tool_name":"Write","tool_input":{"file_path":"/home/nick/dev/node_modules/zod/x.ts"}}' \
  | node hooks/docs-gate.cjs check

# 7c. The unsatisfiable denial, reachable today → must PASS
echo '{"session_id":"qs","tool_name":"Write","tool_input":{"file_path":"/home/nick/dev/.specify/.claude-flow/policy/state.json"}}' \
  | node hooks/docs-gate.cjs check
```

**Expected**: all three emit nothing.

7c is the regression test for a live defect: the `claude-flow` pattern
`(^|\/)\.claude-flow(\/|$)` is **unanchored** and matches `/home/nick/dev/.specify/.claude-flow`,
which exists. Its only hint is `` `claude-flow --help` `` — a command that cannot run because
claude-flow is not installed. **Denial with no way through.** After this feature, `claude-flow`
must not appear in the territory config at all.

---

## Scenario 8 — Gate degrades safely (P3, SC-005, FR-021)

**Proves**: a broken gate asks; it never silently permits.

```bash
printf '' | node hooks/docs-gate.cjs check                 # empty stdin
printf '{' | node hooks/docs-gate.cjs check                # unparseable
mv config/territories.json{,.bak} \
  && echo '{"session_id":"q","tool_name":"Write","tool_input":{"file_path":"/tmp/x"}}' \
     | node hooks/docs-gate.cjs check
mv config/territories.json{.bak,}
```

**Expected**: all three emit `permissionDecision: "ask"`. **None emits nothing.** A silent pass
here is a fail-open bug and blocks the feature.

---

## Scenario 9 — Honest component inventory (P4, SC-007, FR-020, FR-025)

**Proves**: no live configuration references absent tooling.

```bash
./scripts/inventory-flow-refs.sh
```

**Expected**: a per-component table of declared / installed / binaries / live reference count.

Current state: `ruflo` and bare `claude-flow` are **neither declared nor installed**, yet
**183 live files reference them** — ~130 slash commands, 20 skills, 8 agents, 30+ helpers,
plus `proven-config.json` and `statusline.sh`. Each instructs an agent to invoke a binary that
does not exist.

`@claude-flow/codex`, `agentic-flow`, `ruvector`, and the `@ruvector/*` packages are real and
installed — `ruvector` arrives transitively via `agentic-flow`, not as a direct dependency.
`@claude-flow/aidefence` and `@claude-flow/guidance` remain unverified in this pass.

**This is the largest work item in the feature**, not the cleanup it was scoped as. It needs
an operator decision on delete-vs-rewrite per category before it can be sized (open item O-5).

---

## Coverage

| Scenario | Story | Requirements | Criteria | Notes |
|---|---|---|---|---|
| 1 | P1 | FR-001, FR-002, FR-004 | SC-001 | |
| 2 | P1 | FR-006, FR-006b | SC-009 | reproduces a 2026-08-19 passing benchmark |
| 3 | P2 | FR-008 | SC-008 | |
| 4 | P2 | FR-014, FR-014c | — | **load-bearing, no recovery path** |
| 5 | P2 | FR-010, FR-010a, FR-011, FR-011a | SC-003, SC-004 | SC-004 **not met until measured at scale** (O-1) |
| 6 | P3 | FR-016, FR-017, FR-018 | SC-005 | |
| 7 | P3 | FR-019, FR-019a, FR-019b, FR-020 | SC-005, SC-006 | **load-bearing, outage risk** |
| 8 | P3 | FR-021 | SC-005 | |
| 9 | P4 | FR-020, FR-024, FR-025 | SC-007 | blocked on O-5 |

**Not covered by a scenario, assessed separately** (see tasks.md Phase 7):

- **SC-002** — requires a week of both clients writing; assessed at T063, not on day one.
  Scenario 1 checks the weaker precondition that the shared store touches neither client's own
  index (FR-003).
- **SC-010** — an operator-capability judgement, assessed at T061 once the CLI exists.

### Measurement evidence (2026-08-26)

- T064: 10 explicit hybrid recall queries returned a result with a source permalink. This is an initial smoke sample, not a statistical SC-003 claim.
- T064a: capture effectiveness sample is not yet valid because no manually labeled eligible FR-005a candidate set was recorded for these sessions. No capture rate is reported.

### FR-007b measurement procedure (2026-08-26)

Use `agent-memory/scripts/capture-effectiveness.cjs` with a manually curated JSON file containing exactly 10 transcript paths and each session's eligible governed claims. The script counts exact claim presence in projected notes and reports numerator, denominator, per-session rows, and rate. The example fixture is intentionally non-runnable and contains no real transcript path.


### O-1 resolution — real corpus-scale latency measured (2026-08-26, follow-up)

Root cause of the earlier "unmeasured" state: two independent operator errors, not a
missing capability.

1. An ad-hoc diagnostic script connected to `memory.db` directly with Python's `sqlite3`
   and never loaded the `sqlite_vec` extension, so it saw `no such module: vec0` and wrongly
   concluded vector search was broken.
2. The first reindex attempt ran without `BASIC_MEMORY_CONFIG_DIR`, so it targeted the
   default `~/basic-memory` project instead of the live `pilot` project the MCP server uses.

Fix: `BASIC_MEMORY_CONFIG_DIR=/home/nick/.basic-memory-pilot basic-memory reindex --embeddings -p pilot`.
Vector chunk rows went from 67 to 1,727 (1,643 belonging to the 233 backfilled session
notes). A subsequent `search_notes` call through the real MCP tool returned differentiated
similarity scores (0.70–0.73, not the flat 1.0 FTS-only signature), confirming semantic
search is genuinely active.

**Latency**: measured via `basic-memory tool search-notes --hybrid`, the same search path
the MCP tool calls internally, across 10 varied queries at full corpus scale (242 entities,
1,727 vector chunks):

| Stat | Value |
|---|---|
| min | 6.38s |
| median | 7.14s |
| p95 (9th of 10) | 8.02s |
| max | 8.40s |

This **exceeds** the FR-012 target of P95 5s. The CLI path pays ~1.05s of process startup
plus a full fresh embedding-model load on every invocation — costs the persistent MCP
server (loaded once at process start) does not repeat per query. True live-server per-query
latency was not directly measurable from outside the running stdio process. SC-004 is
therefore recorded as **unmet as measured**, not unmeasured — this is real, honest evidence
that the CLI-cold path is too slow for mid-task use, while the actual warm path remains an
open question requiring server-side instrumentation to answer.
