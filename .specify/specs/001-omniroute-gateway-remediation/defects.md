# Defect Register — OmniRoute Gateway

**Created**: 2026-08-25
**Method**: three parallel adversarial reviews, each prompted to refute rather than confirm.
All findings cited to `file:line`, HTTP response, or DB read. Items that could not be
verified are marked UNVERIFIABLE rather than assumed working.

Package root `$PKG` = `/home/nick/.nvm/versions/node/v24.19.0/lib/node_modules/omniroute`

---

## D1 — `auto/best-reasoning` replays foreign-signed thinking blocks ❌ OPEN

**Severity**: P1. ~1,073 hard 400s/day — the largest single failure source on the gateway.

Thinking-block signatures are model-bound. The fallback chain replays a block signed by one
model to another, spread evenly across `claude-opus-5`, `opus-4-6/4-7/4-8`, `sonnet-4-6`
(~207 each). 100% `claude→claude`, combo `auto/best-reasoning` (953 of 1,073).

```
[400] messages.N.content.0: Invalid `signature` in `thinking` block
```

A narrow precedent exists but does not cover this: `$PKG/open-sse/executors/default.ts:601-628`
strips replayed `reasoning_content`, but line 607 gates it to `provider === "mistral"`.

**Fix direction**: strip `thinking` on model switch, or pin reasoning traffic to one model.

---

## D2 — claude→gemini translator emits a body with no messages field ❌ OPEN

**Severity**: P1. 704 errors/day. 100% cross-format `claude→gemini`.

```
[400] Expected input to contain field: 'messages'.
```

Outbound body contains neither `messages` nor `contents`.
Sample: `~/.omniroute/call_logs/2026-08-25/2026-08-25T09-15-52.311Z_1787649345240-c90fb1.json`

Two smaller relatives, same translation path: `Unknown name "encrypted" at
'tools[0].function_declarations[3]'` (85/day) and `thinking: property 'thinking' is
unsupported` (33/day).

---

## D3 — round-robin strategy degraded routing ✅ FIXED 2026-08-25

**Severity**: P1. Self-inflicted earlier the same day; all 4 exercised combos hit 0% success.

Three independent problems, all from source:

1. Rotation is per-request keyed on **combo name only**
   (`$PKG/open-sse/services/combo/rrState.ts:38-46`). Concurrent callers — including
   subagents — share one counter, so models hop mid-conversation.
2. `round-robin` is **absent** from the prompt-cache-affinity allowlist
   (`$PKG/open-sse/services/combo/promptCacheAffinity.ts:262-264`), which contains
   `lkgp`, `priority`, `weighted`, `fill-first`. RR silently disabled prompt caching.
3. RR rotates `cc/*` to the front ~1/N of requests **by design**. Combined with dead free
   members, `cc/*` became 100% of successful traffic — reached on every request after three
   wasted round-trips, rather than as a last resort.

**Fix applied**: strategy `lkgp` on all 7 combos; membership rebuilt from live-verified
healthy providers. Result 24/25 members OK, every combo resolving to `ghm/*`.

**Contributing cause**: members were chosen from a catalog without checking provider health.
`mistral/*` and `cerebras/*` were both `credits_exhausted` (402) at the time of selection.

---

## D4 — `qdrantHost` is an empty string ❌ OPEN

**Severity**: P2. Primary root cause of memory being wholly inert.

`key_value` namespace `settings`: `qdrantEnabled=true`, `qdrantPort=6333`, `qdrantHost=""`.

`$PKG/src/lib/memory/qdrant.ts:80` resolves host as
`settings.qdrantHost.trim() || envHost || ""`, and `QDRANT_HOST` is unset everywhere, so
host is `""`. Five entry points guard on it — `qdrant.ts:185, 284, 353, 413, 443`:

```ts
if (!cfg.enabled || !cfg.host) return { ok: false, latencyMs: 0, error: "not_configured" };
```

Health check, upsert, search, delete and bulk-delete all short-circuit **without issuing a
single HTTP request**. `GET localhost:6333/collections` returns `{"collections":[]}` — the
collection was never created, in the entire lifetime of the deployment.

`memoryVectorStore=qdrant` and `qdrantEnabled=true` cause the UI to report this as ON.

---

## D5 — no embedder resolves under `auto` ❌ OPEN

**Severity**: P2. Independently fatal — fixing D4 alone changes nothing.

`$PKG/src/lib/memory/embedding/index.ts:137-172`, `auto` branch:

| line | condition | live value | result |
|---|---|---|---|
| 139 | `if (providerModel)` | `memoryEmbeddingProviderModel = null` | skipped |
| 152 | `if (settings.staticEnabled === true)` | `false` | skipped |
| 162 | `if (settings.transformersEnabled === true)` | `false` | skipped |
| 172 | — | — | `noSource("auto: no embedding source available")` |

`embed()` at `:186-195` returns this as a **value**, not a throw. Caller `store.ts:130` logs
`memory.vec.embed.fail` at warn level — a string appearing **0 times** in any log.

Note `memoryEmbeddingProviderModel` is a distinct setting from `qdrantEmbeddingModel`;
setting the latter does not feed this chain.

---

## D6 — `qdrantEmbeddingModel` is cross-wired ❌ OPEN

**Severity**: P2. Independently fatal.

Configured: `openrouter/google/gemini-embedding-2`. The `openrouter` provider is healthy
(`provider_connections` `70ccf956-…`, `is_active=1`, `test_status=active`) — the **model id**
is the defect. `$PKG/open-sse/config/embeddingRegistry.ts:203-243` lists exactly seven valid
openrouter embedding ids, and `google/gemini-embedding-2` is not among them.

`gemini-embedding-2` exists only under the separate `gemini` provider (`:247-266`), which
uses a different baseUrl and a `gemini-embed-content` protocol.

**Latent companion**: `qdrant.ts:118-124` defaults `vectorSize` to 1536; `gemini-embedding-2`
emits 768 (`embeddingRegistry.ts:255-259`). Every upsert would 4xx once D4/D5 are fixed.

---

## D7 — extraction is regex-based and produces nothing ❌ OPEN

**Severity**: P2. Independently fatal.

`$PKG/src/lib/memory/extraction.ts` is pattern-matching, not LLM-based.

```
memory.extraction.start   268
memory.stored               1
```

The `memories` table holds **one** row, dated 2026-08-04, content
`"the read_file tool to get the code"` — a regex artifact, not a fact. `memory_vec_meta`
holds one row with null vector columns.

---

## D8 — vector write failures are structurally silent ❌ OPEN

**Severity**: P2. The reason D4–D7 went unnoticed for weeks.

`$PKG/src/lib/memory/store.ts:232-236` and `:298-302` fire-and-forget:

```ts
.then((r) => { if (r.ok) log.debug?.("qdrant.upsert.ok", …) else log.warn?.("qdrant.upsert.fail", …) })
.catch((e) => log.warn?.("qdrant.upsert.error", { id, error: String(e) }));
```

Never awaited, so the request path never observes failure. `not_configured` is a returned
value rather than a throw, so `retrieval.ts:383`'s catch-based warn never fires either.

Log counts across `app.log` and `app.2026-08-20_021912.log`: `qdrant.upsert.*` = **0**,
`memory.vec.embed.fail` = **0**, literal `qdrant` anywhere = **0**. Neither successes nor
failures. Meanwhile `memory.retrieval.complete` fired 219 times, 227/227 with `count:0`.

Retrieval **wiring** is intact and is the one healthy component:
`$PKG/open-sse/handlers/chatCore.ts:1065` → `memorySkillsInjection.ts:114,123-124` genuinely
mutates the outgoing body. It faithfully injects an empty list.

---

## D9 — compression toggles are decoration; clearing the combo is dangerous ❌ OPEN

**Severity**: P3 as configured, **P1 if "fixed" naively**.

`$PKG/open-sse/.../resolveCompressionPlan.ts:15-20` returns on the active-combo branch
*before* `deriveDefaultPlan` is reached. Live `activeComboId="default-caveman"` = `[rtk,
caveman]`. Telemetry across 197,653 rows shows **zero rows ever** for `ccr`, `session-dedup`,
`llmlingua`, `codex-responses`. The eight UI toggles do nothing; the real pipeline is
`rtk → caveman`.

**The trap**: the intuitive fix for dead toggles — clearing `activeComboId` — hands dispatch
to `deriveDefaultPlan` and arms all eight engines, including `ccr` (destroys ≥600-char blocks
unrecoverably) and `session-dedup` (missing `__sessionDedupMap__` reconstructor), with
`fidelityGate` absent so `fidelityGateStep.ts:27` fails open. `activeComboId` is currently
load-bearing safety. Disable `ccr` and `session-dedup` *first* if it is ever cleared.

---

## D10 — `caveman` is net overhead ❌ OPEN

**Severity**: P3.

Its own `validateCompression` (`caveman.ts:546-553`) rejects and reverts its output on
**65,801 of 88,047 rows (74.7%)**. Lifetime saving 2.76M tokens against `rtk`'s 2.00B —
0.14% of the total. The surviving quarter is applied at `ultra` intensity
(`engines.caveman.level` overrides the displayed `cavemanConfig.intensity:"lite"` via
`strategySelector.ts:733-742`) to `compressRoles:["user"]` — the user's literal typed
instructions.

`rtk` does essentially all real work and is the only engine honouring `cache_control`
(`rtk/index.ts:401,420`), though `maxLinesPerResult:120` deletes tool output aggressively.

**Compression is exonerated on the 400s**: 84.1% of successful calls were compressed versus
28.3% of thinking-signature failures, and 654 of those 400s occurred in hours where
`compression_analytics` logged zero runs.

---

## D11 — `responseValidation` never executes for Claude Code ❌ OPEN

**Severity**: P3 — currently inert, harmful if activated as written.

Evaluated at `$PKG/open-sse/services/combo/validateQuality.ts:592-593`, inside the
**non-streaming** branch. The streaming branch returns earlier with its own Claude-lifecycle
peek (`:236`). Claude Code streams, so `forbiddenSubstrings` and `minContentLength` are never
evaluated for real traffic.

Were it to apply, `minContentLength: 1` would be actively harmful:
`responseValidation.ts:115-137` `extractContentText` reads only `choices[].message.content`
and **ignores `tool_calls`**. A tool-call-only assistant turn has `content: null` → extracts
`""` → length 0 < 1 → marked invalid → failover, breaking precisely the agentic tool-calling
the design exists to protect.

**Decision**: left unset deliberately. Do not "restore" it without fixing the extractor.

---

## D12 — task detection misroutes agentic continuation turns ❌ OPEN

**Severity**: P2.

`$PKG/open-sse/services/taskAwareRouter.ts:304-343` — `detectTaskType` does case-insensitive
substring matching over one system message and the last user message.

`extractText` (`:281-291`) maps array parts via `part?.text`. Anthropic `tool_result` blocks
have no `.text`, so `userText` becomes `""` on every tool-result continuation turn — the bulk
of an agentic session — matching nothing and defaulting to `chat`. Turn 1 lands on
`task-coding`, turn 2 on `task-chat`. Different combos, so session stickiness cannot span it.

Secondary: pattern collisions (`"write a script"` matches both coding `:49` and creative
`:79`); bare substrings like `"implement"`, `"debug"` match anywhere in a long system prompt;
`background` is tested first, so `"brief description"` diverts ordinary prompts.

Also `applyTaskAwareRouting` (`:352-380`): the "conservative heuristic" guard at `:371-376`
is an **empty `if` block containing only comments**, so the override is unconditional. Live
stats `"detected":88,"routed":88` — 100%. Every explicitly pinned model is discarded, which
contradicts the workspace's "client pins, gateway routes" design.

**Mitigation in place**: `task-chat` carries a `cc/*` backstop precisely because misrouted
agentic turns land there.

---

## D13 — fabricated environment variables in `~/.omniroute/.env` ✅ DIAGNOSED

**Severity**: P3. Inert but actively misleading.

`~/.omniroute/.env` contains four variables that **do not exist anywhere in the source**:
`OMNIROUTE_MEMORY_VECTOR_STORE`, `OMNIROUTE_QDRANT_URL`, `OMNIROUTE_LLM_PROVIDER`,
`OMNIROUTE_OLLAMA_URL`. Zero grep hits across the package. They originate from an LLM
suggestion, not documentation.

`OMNIROUTE_QDRANT_URL` is the harmful one: it makes the Qdrant host *appear* configured while
the code reads only `QDRANT_HOST`/`QDRANT_PORT` — masking D4.

Real surface: `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`,
`QDRANT_EMBEDDING_MODEL`, `QDRANT_VECTOR_SIZE`, `QDRANT_HNSW_EF_CONSTRUCT`. Backend selection
is a **DB setting** (`vectorStore`: `sqlite-vec|qdrant|auto`, `memory/settings.ts:63`), not an
env var. A global npm install still loads `~/.omniroute/.env` — no `~/.bashrc` export is
needed, contrary to the same suggestion.

---

## Non-defects — recorded to prevent false "fixes"

- **Double vendor segment is correct.** `nvidia/nvidia/nemotron-3-ultra-550b-a55b` is the
  real catalog id. An earlier review reported it as a typo; that finding was an artifact of
  an abbreviated review prompt and is **retracted**. Do not collapse it to a single `nvidia/`.
- **Combo test result field is `status: "ok"`**, not `success`. Parsing the wrong field
  reports a false 0% across all combos.
- **`PUT /api/combos/{id}` only.** `PATCH` returns 405; `POST` with an existing name returns
  `COMBO_004` name conflict.
- **`src/domain/comboResolver.ts` is dead code** — zero importers under `src/` or `open-sse/`.
  It contains a clean `case "round-robin"` counter that does not reflect runtime behaviour.
  Do not reason from it.

---

## Unverifiable — explicitly not assumed working

- **Per-model tool-calling and parallel-tool-use support.** `/api/models` returns only
  `{provider, model, name, fullModel, alias, available}` across 302 models. No capability
  field exists. Agentic suitability of every combo member is an assumption.
- **Context-window sizes and overflow behaviour.** No `contextLength` field in `/api/models`
  or `freeModelCatalog.data.ts`; no overflow preflight found in the dispatch path read.
  Whether overflow hard-errors or silently truncates is untested.
- **`ghm` success rate.** `/api/provider-metrics` has no `ghm` entry (it lists
  `github-models`). Health is inferred from live combo tests only.
- **`claude` provider's own 42% success rate** (2,073 requests, 869 successes,
  `lastErrorStatus 400`) — not investigated; likely overlaps D1/D2 but unconfirmed.
