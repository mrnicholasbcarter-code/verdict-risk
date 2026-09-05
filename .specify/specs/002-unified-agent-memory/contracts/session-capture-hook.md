# Contract: session-capture hook

**Executable**: `/home/nick/dev/agent-memory/hooks/session-capture.cjs`
**Event**: `SessionEnd`
**Mode**: `async: true` — fire-and-forget
**Requirements**: FR-007, FR-008, FR-010, FR-010a, FR-011, FR-014

Projects a session transcript to redacted markdown and writes it into the watched notes
directory. The running basic-memory filesystem watcher indexes it in ~1 s. The hook never
speaks MCP, never authenticates, and never blocks.

---

## Wiring

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/home/nick/dev/agent-memory/hooks/session-capture.cjs",
            "async": true
          }
        ]
      }
    ]
  }
}
```

**No matcher.** Every termination is captured — `clear`, `resume`, `logout`,
`prompt_input_exit`, `other`. This is deliberate beyond simplicity: the stdin field carrying
the termination reason is **UNVERIFIED** (open item O-2 — the published page truncates before
the `SessionEnd` payload on both a plain and an anchored fetch). Omitting the matcher removes
the dependency entirely. If per-reason behaviour is ever wanted, confirm the field name from
the live page first.

`async` is a **command-hook-only** field, a sibling of `type` and `command` in the inner
`hooks` array. It is not available on `http`, `mcp_tool`, `prompt`, or `agent` handlers.

### Why `async` and not `mcp_tool`

`async: true` "runs in the background without blocking" — this is precisely what satisfies
**FR-008**: capture adds 0 ms to the blocking path and sidesteps the 1.5 s shared `SessionEnd`
budget entirely.

An `mcp_tool` handler writing straight to basic-memory was rejected as the primary path: it
cannot redact (FR-014 requires transformation **before** write), and a synchronous MCP
round-trip inside a 1.5 s shared budget is hostile.

A long-running indexer daemon was rejected outright — that is the exact shape that already
failed here. Claude-mem 13.15.2 "captured prompts but produced zero observations; its isolated
provider process could not inherit interactive OAuth." **The automatic write-through
capability has been attempted once and failed on authentication, not on concept.** A command
hook runs as the user, in the user's environment, and needs no credentials at all.

`asyncRewake` is **not** used — a capture failure should not wake Claude.

---

## Input (stdin, JSON)

| Field | Use |
|---|---|
| `session_id` | Note title component and `provenance`. |
| `transcript_path` | **Read directly.** The hook derives no path. |
| `cwd` | Project slug for the title. |
| `hook_event_name` | Sanity check; must be `SessionEnd`. |

`transcript_path` being supplied means the hook never needs to know that transcripts live at
`<slug>/<sessionId>.jsonl` or that the slug is cwd with `/` → `-`.

## Output

**None.** No stdout, no stdout JSON, exit 0 always. An `async` hook cannot block or contribute
a decision, so output would be discarded. Failures go to stderr and the exit code, for the
operator, not for Claude.

---

## Processing

### Step 1 — Parse

One JSON object per line. Skip unparseable lines rather than aborting; a truncated final line
is normal when a session ends abruptly.

**Roles are not top-level.** The payload nests at `.message`, with `.message.role` and
`.message.content`.

### Step 2 — Project

Select exactly three inputs:

| Input | Selector |
|---|---|
| Compaction summaries | `isCompactSummary === true` on a `type:"user"` record |
| Human prompts | `type:"user"` **without** `toolUseResult` and **without** `isCompactSummary` |
| Assistant prose | blocks with `type === "text"` in `.message.content` |

Discard: `toolUseResult` (42% of bytes), `attachment` records (20%), `tool_use` blocks (17%),
`thinking` blocks. Result is ≈8% of corpus bytes, dropping ≈79% noise.

> **There is no `type:"summary"` record** — 0 hits across 60 files. A projection keyed on it
> silently indexes nothing. The field is `isCompactSummary` on a user record.

All three inputs are required. Compaction summaries appear in only **44 of 233** transcripts,
so summaries alone would leave 189 sessions unrecallable, failing FR-010a.

Subagent turns are **not** in the parent file — `isSidechain` was true 0 times. They live at
`<slug>/<sessionId>/subagents/agent-<id>.jsonl`. Out of scope unless the parent projection
proves insufficient.

### Step 3 — Redact (FR-014)

Apply every rule to the projection. Mask as `⟨redacted:<rule-id>⟩`.

Confirmed present: `ANTHROPIC_AUTH_TOKEN` — 641 occurrences across 32 files, **152 followed by
a real value across 25 files**, 115 at length 35.

Retained defensively despite 0 hits today: `sk-ant-*`, `ghp_*`, `gho_*`, `AKIA*`,
`Bearer <…>`, PEM blocks, JWTs.

**Fail closed.** Re-scan the rendered output; if any rule still matches, **do not write**, log
to stderr, exit non-zero. Skipping one session note is recoverable — an indexed credential is
not. There is no post-hoc removal: `embed: false` excludes semantic indexing only and leaves
content in FTS.

### Step 4 — Render

Markdown per [`knowledge-note.schema.md`](./knowledge-note.schema.md), `type: session`.
Chronological order.

### Step 5 — Write

```text
/home/nick/.basic-memory-pilot/notes/sessions/<project-slug>-<date>-<short-session-id>.md
```

- `sessions/` — **no path part may begin with `.`** or the watcher skips it.
- **Must be `.md`.** Non-markdown is indexed as metadata only — title, checksum, size, mime —
  with no FTS rows and no embeddings.
- Write to a temp file in the same directory, then `rename()`. The watcher debounces at 1000
  ms; a partial file racing the watcher would index truncated content.
- **Never overwrite an existing note.** If the target exists, exit 0 without writing — a
  session is captured once.

---

## Test obligations

| # | Scenario | Expected |
|---|---|---|
| T1 | transcript containing a known token value | output contains `⟨redacted:` and **no** occurrence of the value |
| T2 | projection that still matches a rule after redaction | nothing written, non-zero exit |
| T3 | transcript with 0 compaction summaries | note still produced from prompts + prose |
| T4 | transcript with an unparseable final line | note produced, line skipped |
| T5 | target note already exists | exit 0, file unmodified |
| T6 | write is interrupted mid-render | no partial `.md` visible in `sessions/` |
| T7 | 11.8 MB transcript | output ≈8% of input bytes; no `toolUseResult` content present |
| T8 | note written | appears in `search_notes` within ~2 s |

T1 and T2 are the load-bearing tests. Everything else is recoverable.
