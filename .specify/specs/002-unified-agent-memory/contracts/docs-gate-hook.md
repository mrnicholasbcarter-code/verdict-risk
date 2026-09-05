# Contract: docs-gate hook

**Executable**: `/home/nick/dev/agent-memory/hooks/docs-gate.cjs`
**Events**: `PreToolUse` (mode `check`), `PostToolUse` (mode `receipt`)
**Requirements**: FR-017, FR-019, FR-019a, FR-019b, FR-020, FR-021, FR-022, FR-023

Migrated from `~/.claude/hooks/docs-gate.cjs` unmodified, then changed. The existing gate
works; this contract records what it already guarantees and what changes.

---

## Input (stdin, JSON)

Only three fields are consumed (`:127-129`). Every other stdin field is ignored.

| Field | Type | Use |
|---|---|---|
| `session_id` | string | Receipt directory name. Falls back to the literal `nosession`. |
| `tool_name` | string | Selects Bash parsing (`:108`) and, new, the MCP receipt branch. |
| `tool_input` | object | Target extraction. For MCP docs tools, carries `library`. |

## Output (stdout, JSON)

`pass()` writes **nothing** and exits 0 (`:102`).

`deny()` / `ask()` write the object below and **also exit 0** (`:95-101`) — the decision rides
in stdout JSON, never in the exit code. A non-zero exit is a crash, not a denial.

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "<human-readable, includes territory hints>"
  }
}
```

`permissionDecision` is `"deny"` or `"ask"`.

---

## Guaranteed behaviour

### Fail-to-ask (FR-021 — already satisfied)

Three triggers, all producing `ask`, never `deny` and never a silent pass:

| Trigger | Line |
|---|---|
| empty stdin | `:122` |
| unparseable JSON | `:125` |
| any uncaught throw in `main()` | `:168` |

**The gate never fails open.** A broken gate asks; it does not silently permit.

### `check` mode — `PreToolUse` (`:148-164`)

For each target with `write: true`: resolve `ownerOf(path)`. If owned **and enforced** and no
receipt exists → `deny` with `docHints()`.

### `receipt` mode — `PostToolUse` (`:131-146`)

| # | Trigger | Receipt granted for | Status |
|---|---|---|---|
| 1 | `Read` of a file under a territory root (`:133-137`) | owning territory | existing |
| 2 | `Bash` matching `([a-z0-9@/._-]+)\s+--help` and not matching `WRITE_RE` (`:138-143`) | `basename($1)` | existing |
| 3 | `tool_name` matching `mcp__docs-mcp-server__.*` | `tool_input.library` | **NEW** |

---

## Changes required

### C1 — Accept an MCP docs query as a receipt (FR-017)

Add a third branch in `receipt` mode. No MCP tool name is recognised anywhere in the gate
today; `tool_name` is consulted only to decide Bash parsing (`:108`).

```js
// receipt mode, after the Bash branch (~L143)
if (/^mcp__docs-mcp-server__/.test(tool_name)) {
  const lib = tool_input && tool_input.library;
  if (lib) writeReceipt(session_id, lib, `docs-mcp query ${new Date().toISOString()}`);
  return pass();
}
```

**Keyed on the input, not the result.** `search_docs` returns plain prose — `Result N: <url>`
plus markdown — with no structured library or version field. The input carries `library`; the
output does not.

**Settings matcher must be `mcp__docs-mcp-server__.*`.** The trailing `.*` is required: a
matcher like `mcp__docs-mcp-server` is compared as an exact string and matches no tool.

**Why observation, not verification.** All three store-based routes fail — the Docker volume
`docs-mcp-data` is root-owned and unreadable by the hook's user; the schema
(`libraries, versions, pages, documents, metadata, documents_fts*, documents_vec*`) has **no
query, search, audit, or log table**, so the DB never records that a search occurred; and
`GET /api` returns `{"error":"Not Found"}`. Observation is not a compromise — it is the only
mechanism, and it is complete.

### C2 — Externalise the territory list (FR-022)

Replace the inline `const` at `:21-25` with a load of
`/home/nick/dev/agent-memory/config/territories.json`
(schema: [`territories.schema.json`](./territories.schema.json)). A malformed or
unrecognised-version file must throw, which `:168` converts to `ask` — degrading safely
without failing open.

### C3 — Constrain `PKG_RE` to the allowlist (FR-019b)

`ownerOf` (`:32-40`) falls through to `PKG_RE` (`:27`), making **any** `**/node_modules/<pkg>`
path a territory owned by `<pkg>`. Under blocking enforcement with two indexed libraries, that
is an outage on the first write into any package directory.

Gate the fall-through on `packageTerritories.mode` and on the resolved id having
`enforced: true`. **Without C3, FR-019b's "`omniroute` alone" is unreachable regardless of the
territory list.**

### C4 — Remove absent territories (FR-020)

Drop `ruflo` and bare `claude-flow`. Neither is declared or installed. The `claude-flow`
pattern `(^|\/)\.claude-flow(\/|$)` is **unanchored** and matches
`/home/nick/dev/.specify/.claude-flow`, which exists — so writing there demands a
`claude-flow` receipt whose only hint is `` `claude-flow --help` ``, a command that cannot
run. **An unsatisfiable denial, reachable today.** The schema forbids both ids outright.

### C5 — Anchor all patterns

Every `patterns` entry must anchor to a path root or a complete segment.

---

## Unchanged

- Receipt path scheme `~/.claude/.docs-receipts/<session_id||'nosession'>/<tool with [/@]→_>`
  (`:42-44`).
- Receipt content is **never parsed** — existence is the only test (`:45-47`).
- **No expiry, no TTL.** A receipt lasts the session directory's lifetime. 9 persist today.
  Deliberate: FR-019a forbids a per-invocation override, so a re-prompt loop within one
  session would be friction with no safety gain.

---

## Test obligations

| # | Scenario | Expected |
|---|---|---|
| T1 | empty stdin | `ask` |
| T2 | `{` (unparseable) | `ask` |
| T3 | territories.json missing | `ask` (via `:168`) |
| T4 | Write under an `enforced: true` territory, no receipt | `deny`, reason names the territory and a hint that resolves |
| T5 | same, after `mcp__docs-mcp-server__search_docs` with `library: "omniroute"` | `pass` (no stdout) |
| T6 | Write under `node_modules/<some-unlisted-pkg>` | `pass` — proves C3 |
| T7 | Write under `/home/nick/dev/.specify/.claude-flow` | `pass` — proves C4 |
| T8 | Write under an `enforced: false` territory (`zod`) | `pass` |
| T9 | config listing `ruflo` | startup throws → `ask` |
| T10 | `mcp__docs-mcp-server__search_docs` with no `library` | `pass`, no receipt written |
