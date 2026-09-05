# Phase 1 Data Model

**Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

Entities derive from the spec's Key Entities section, constrained by what basic-memory
actually stores (research R2) and what transcripts actually contain (research R3).

---

## 1. Knowledge Record

A single durable, cross-client unit of knowledge. Persisted as one basic-memory note.

| Field | Type | Required | Source / Constraint |
|---|---|---|---|
| `permalink` | string | yes | Assigned by basic-memory as `{project}/{folder}/{kebab-title}`; `permalinks_include_project: true`. Unique per project (`uix_entity_permalink_project`). Not author-supplied. |
| `title` | string | yes | Note title. Kebab-cased into the permalink. |
| `note_type` | enum | yes | **`decision` \| `verified-fact` \| `refuted-claim` \| `correction`** — exactly the four classes FR-005a permits. Free text in basic-memory but indexed (`ix_note_type`), so it filters efficiently. |
| `status` | enum | yes | `active` \| `superseded` \| `disputed`. Mandated by the 2026-08-19 prior-art note (research R1). |
| `provenance` | string | yes | Where the knowledge came from: a session id, a file path with line range, a command, or a URL. Prior art requires it. |
| `observed_at` | ISO-8601 | when known | Time the fact was observed, distinct from write time. Prior art requires it. |
| `confidence` | enum | yes | `verified` \| `reported` \| `inferred`. Prior art requires it. `verified` is reserved for direct observation, matching FR-005a's definition of a verified fact. |
| `evidence` | string | for `verified-fact` and `refuted-claim` | The observation itself — output, schema excerpt, or quoted doc. FR-005a requires evidence for both classes. |
| `rationale` | string | for `decision` | The why. FR-005a requires it. |
| `body` | markdown | yes | Note content. Must be markdown or basic-memory indexes metadata only (research R2). |
| `embed` | boolean | no | Defaults true. **Setting false excludes semantic indexing only; content stays in FTS.** Never a secrecy control (research R2). |

### Validation rules

- `note_type` outside the four-value enum is rejected at write time (FR-005a bounds the store).
- `confidence: verified` requires non-empty `evidence`.
- `note_type: decision` requires non-empty `rationale`.
- All fields pass through redaction before write (FR-014). Redaction is not optional and not
  reversible after the fact.
- Writing to an existing permalink errors by default (`write_note_overwrite_default: false`).
  Updates use `edit_note`; supersession creates a new note (see state transitions).

### State transitions

```text
                    ┌──────────────┐
   write_note  ───► │    active    │
                    └──────┬───────┘
                           │
      new note contradicts │ new note covers same subject,
      and is authoritative │ neither is authoritative
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
      ┌──────────────┐          ┌──────────────┐
      │  superseded  │          │   disputed   │
      └──────────────┘          └──────────────┘
```

- **active → superseded**: the new note gains a `supersedes` relation to the old; the old is
  edited to `status: superseded` and gains `superseded_by`. Both notes are retained — FR-006
  forbids overwriting.
- **active → disputed**: both notes are marked `disputed` and gain a `contradicts` relation.
  **Neither is deleted and no winner is picked, including by recency** (FR-006). Recall must
  return both together, flagged. The 2026-08-19 benchmark already demonstrated exactly this
  behaviour with conflicting values `42` and `57`.
- **superseded → active** is not permitted; correcting a supersession means writing a new
  active note.

### Relations

basic-memory has a `relation` table (`from_id`, `to_id`, `to_name`, `relation_type`) with
free, indexed `relation_type`, and `to_name` holds unresolved forward references — so a note
may link to one that does not exist yet.

| `relation_type` | Meaning |
|---|---|
| `supersedes` / `superseded_by` | Authoritative replacement. |
| `contradicts` | Mutual, unresolved. Drives the `disputed` flag. |
| `evidence_for` | Links a record to the session note that produced it. |

**There is no native supersede or contradiction concept in basic-memory (research R2).** These
are conventions this feature defines and must therefore enforce in its own write path.

---

## 2. Session Transcript

The read-only recall substrate. Never modified by this feature.

| Field | Type | Source |
|---|---|---|
| `session_id` | string | **The filename** — `<slug>/<sessionId>.jsonl`. Session id → path is a string join; no index required (research R3). Also supplied directly on hook stdin. |
| `project_slug` | string | Directory name; cwd with `/` → `-` (`/home/nick/dev` → `-home-nick-dev`). |
| `transcript_path` | absolute path | Supplied directly on hook stdin — the hook derives nothing. |
| `cwd`, `gitBranch`, `version` | string | Per-record fields. |
| `started_at` / `ended_at` | ISO-8601 | First and last record `timestamp`. |

### Record shape (per line)

One JSON object per line. `uuid` / `parentUuid` thread the conversation as a linked list.
**Roles are not top-level** — the payload nests at `.message`, with `.message.role` and
`.message.content`. Assistant records add `requestId` and `.message.model`; content is an
array of typed blocks (`text`, `tool_use`, `thinking`). Tool results arrive as `type:"user"`
records carrying a top-level `toolUseResult`.

### Derived: Curated Projection

What is actually indexed. Three inputs, because no single one suffices (see plan Complexity
Tracking):

| Input | Selector | Share of corpus bytes |
|---|---|---|
| Compaction summaries | `isCompactSummary === true` on a `type:"user"` record | present in **44 of 233** files; 238 KB across 5 in one 11.8 MB file |
| Human prompts | `type:"user"` **without** `toolUseResult` and **without** `isCompactSummary` | 1.4% (169 KB, 91 prompts in an 11.8 MB file) |
| Assistant prose | `text` blocks in `.message.content` | 4.4% |

**Excluded**: `toolUseResult` (42%), `attachment` records (20%), `tool_use` blocks (17%),
`thinking` blocks. Total projection ≈8% of bytes, dropping ≈79% noise.

> There is **no** `type:"summary"` record — 0 hits across 60 files. The field is
> `isCompactSummary` on a user record. A projection keyed on `type:"summary"` silently
> indexes nothing.

Subagent turns are **not** in the parent file (`isSidechain` was true 0 times). They live at
`<slug>/<sessionId>/subagents/agent-<id>.jsonl`. Projecting them is in scope only if the
parent projection proves insufficient; not assumed.

---

## 3. Session Note

A Curated Projection rendered as one basic-memory markdown note. This is the capture output.

| Field | Value |
|---|---|
| `folder` | `sessions/` — **no path part may begin with `.`** or the watcher skips it (research R2). |
| `title` | `<project_slug> <started_at date> <short session id>` |
| `note_type` | `session` |
| `provenance` | the `session_id` |
| `observed_at` | session `ended_at` |
| `confidence` | `verified` — the transcript is a direct record |
| `body` | projection, in chronological order, **fully redacted** |

Format must be markdown: non-markdown files are indexed as metadata only (title, checksum,
size, mime) with no FTS rows and no embeddings.

---

## 4. Redaction Rule

Applied to every byte before it reaches disk. Not a filter over an existing index — there is
no such thing here (`embed: false` leaves content in FTS).

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable rule name, appears in the masked placeholder. |
| `pattern` | regex | Matches the secret. |
| `replacement` | string | e.g. `⟨redacted:anthropic-auth-token⟩`. |

**Confirmed present in the corpus** (research R3): `ANTHROPIC_AUTH_TOKEN` — 641 occurrences
across 32 files, **152 followed by an actual value across 25 files**, 115 at length 35.

**Confirmed absent but retained defensively** (0 hits each): `sk-ant-*`, `ghp_*`, `gho_*`,
`AKIA*`, `Bearer <…>`, PEM blocks, JWTs. Absence today is not absence tomorrow.

**Invariant**: a projection that still matches any rule after redaction must not be written.
Fail closed — skipping one session note is recoverable; an indexed credential is not.

---

## 5. Territory

An enforcement scope owned by a documentation library. Externalised to a config file, which is
what satisfies FR-022 — today the list is an inline `const` at `docs-gate.cjs:21-25`.

| Field | Type | Notes |
|---|---|---|
| `id` | string | Library name as docs-mcp-server knows it — must match `search_docs`' `library` input, since that is what the receipt is keyed on. |
| `patterns` | regex[] | Paths owned. **Must be anchored.** The existing `claude-flow` pattern `(^\|\/)\.claude-flow(\/\|$)` is unanchored and matches `/home/nick/dev/.specify/.claude-flow`, producing an unsatisfiable denial today (research R5). |
| `enforced` | boolean | **Blocking only when documentation is indexed.** Initial `true` set: `omniroute` alone (FR-019b). |
| `hints` | string[] | Shown in the denial reason. Must never name a command that does not exist — the current `claude-flow --help` hint does. |

### Validation rules

- A territory with `enforced: true` and no corresponding entry in `list_libraries` is a
  configuration error and must fail loudly at gate startup.
- `ruflo` and bare `claude-flow` **must not appear at all** (FR-020) — neither is installed.
- Every `patterns` entry must be anchored to a path root or a full segment.

### The `PKG_RE` correction

`ownerOf()` (`docs-gate.cjs:32-40`) falls through to `PKG_RE` (`:27`), making **any**
`**/node_modules/<pkg>` path a territory owned by `<pkg>`. The real enforced surface is three
directories **plus every installed package** — hundreds of territories against two indexed
libraries. `PKG_RE` must be constrained by the same `enforced` allowlist, or FR-019b's
"`omniroute` alone" is unreachable no matter what the territory list says.

---

## 6. Docs Receipt

Proof that documentation was consulted this session. Existing scheme, unchanged in shape.

| Field | Value |
|---|---|
| path | `~/.claude/.docs-receipts/<session_id \|\| 'nosession'>/<tool with [/@] → _>` (`:42-44`) |
| content | ≤500-char note. **Never parsed — existence is the only test** (`:45-47`). |
| lifetime | **None. No expiry, no TTL.** 9 session dirs persist today. |

### Grant paths

| # | Trigger | Status |
|---|---|---|
| 1 | `Read` of a file under a territory root | exists (`:133-137`) |
| 2 | `Bash` matching `([a-z0-9@/._-]+)\s+--help`, non-write | exists (`:138-143`) |
| 3 | **`PostToolUse` observing `mcp__docs-mcp-server__*`**, keyed on `tool_input.library` | **new** |

Grant 3 must read the **input**, not the result: `search_docs` returns plain prose with no
structured library or version field (research R6). The input carries `library`; the output
does not.

Store-based verification is impossible on principle, not merely on permissions: the
docs-mcp-server schema (`libraries, versions, pages, documents, metadata, documents_fts*,
documents_vec*`) contains **no query, search, audit, or log table** — it stores the corpus and
never records that a search occurred. The Docker volume being root-owned is a second,
independent blocker. Observation is the only mechanism, and it is sufficient.

---

## 7. Component Inventory Entry

One row per flow-stack component, backing the honest-inventory user story (P4).

| Field | Type |
|---|---|
| `name` | string |
| `declared` | boolean — present in a `package.json` |
| `installed` | boolean — present in `node_modules` |
| `binaries` | string[] — present in `node_modules/.bin` |
| `live_reference_count` | integer — non-backup files naming it |
| `disposition` | `retain` \| `remove` \| `pending-decision` |

Current state (research R7): `ruflo` and bare `claude-flow` are **not declared and not
installed**, yet **183 live files reference them**. `@claude-flow/codex`, `agentic-flow`,
`ruvector` and the `@ruvector/*` packages are installed and real. `@claude-flow/aidefence` and
`@claude-flow/guidance` are **UNVERIFIED** this pass and carry `disposition:
pending-decision`.
