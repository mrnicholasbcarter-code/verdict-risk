# Feature Specification: OmniRoute Gateway Remediation

**Feature Branch**: `001-omniroute-gateway-remediation`
**Created**: 2026-08-25
**Status**: Draft — US1 delivered, US2–US5 not started
**Input**: Conserve the paid `cc/claude-*` subscription for work that warrants a frontier
model, route everything else to healthy free providers, and stop the gateway's ongoing
hard-failure bleed.

## Scope Note

This spec is written **retrospectively** for work already performed on 2026-08-25 (US1),
and **prospectively** for the defects that adversarial review surfaced but which remain
unfixed (US2–US5). The distinction is marked per story. Nothing in US2–US5 has been
implemented.

## Evidence Base

Every claim below is sourced from one of:
- installed source at `/home/nick/.nvm/versions/node/v24.19.0/lib/node_modules/omniroute` (v3.8.49)
- live gateway API on `http://localhost:20128`
- `~/.omniroute/storage.sqlite` (read-only), `~/.omniroute/logs/`, `~/.omniroute/call_logs/`

Three independent adversarial reviews were run on 2026-08-25, each prompted to **refute**
rather than confirm. Findings are cited by `file:line` or HTTP response throughout.

---

## User Scenarios & Testing

### User Story 1 - Route routine work to free providers (Priority: P1) ✅ DELIVERED

Nick runs Claude Code against the gateway all day. Routine coding, summarization, and chat
must land on free providers so the paid `cc/claude-*` quota survives for interactive work.

**Why this priority**: This was the originating request. Also the only story where a
regression was actively making things worse — see Defect D3.

**Independent Test**: `POST /api/combos/test {"comboName":"task-<type>"}` for all 7 types;
assert `status == "ok"` for a majority of members and that `resolvedBy` names a free model.

**Acceptance Scenarios**:

1. **Given** task routing enabled, **When** any of the 7 task types is dispatched, **Then**
   the resolved target is a free-provider model, not `cc/*`.
2. **Given** a combo whose first member's provider is failing, **When** a request arrives,
   **Then** the strategy promotes the last-known-good free provider rather than rotating
   into `cc/*`.
3. **Given** a multi-turn agentic session, **When** turn 2+ arrives, **Then** the target
   does not hop to a different model mid-conversation.

**Status**: Delivered 2026-08-25. 24/25 members healthy; all 7 combos resolve to `ghm/*`.

---

### User Story 2 - Stop the thinking-signature failure bleed (Priority: P1) ❌ NOT STARTED

The `auto/best-reasoning` combo replays `thinking` blocks to a model that did not sign them.
Thinking-block signatures are model-bound, so every failover is a guaranteed HTTP 400.

**Why this priority**: Largest single source of failure on the gateway at ~1,073 errors/day.
Pure loss with no tradeoff — nothing is gained by the current behaviour. Independent of all
other stories.

**Independent Test**: Force a failover within `auto/best-reasoning` and assert the outbound
body for the second model contains no `thinking` block signed by the first.

**Acceptance Scenarios**:

1. **Given** a reasoning request that fails over between two Claude models, **When** the
   second request is built, **Then** it contains no foreign-signed `thinking` block.
2. **Given** a day of normal traffic, **When** errors are counted, **Then**
   `Invalid \`signature\` in \`thinking\` block` occurrences are zero.

---

### User Story 3 - Make conversational memory actually function (Priority: P2) ❌ NOT STARTED

Memory reports ON in the UI but has never stored or retrieved anything.

**Why this priority**: High value, but it is currently inert rather than harmful — it
degrades quality silently instead of failing requests. Ranks below the active bleeds.

**Independent Test**: Hold a conversation, then assert the Qdrant collection exists and
holds a non-zero point count, and that a later retrieval returns `count > 0`.

**Acceptance Scenarios**:

1. **Given** a completed conversation, **When** extraction runs, **Then** at least one
   non-artifact memory row is written.
2. **Given** stored memories, **When** a related conversation begins, **Then** retrieval
   returns `count > 0` and the injected body contains the retrieved text.

**Note**: Four blockers are each independently fatal. Fixing fewer than all four produces
no observable change. See Defects D4–D7.

---

### User Story 4 - Remove compression overhead (Priority: P3) ❌ NOT STARTED

The `caveman` engine rejects and reverts its own output 74.7% of the time while saving
0.14% of total tokens.

**Why this priority**: Small, safe, low-value. Genuinely optional.

**Independent Test**: Disable `caveman`; assert token totals move <1% and no new errors.

**Acceptance Scenarios**:

1. **Given** `caveman` disabled, **When** traffic runs, **Then** user-role prompts reach
   the model unmodified and total token savings drop by no more than 1%.

---

### User Story 5 - Make configuration state legible (Priority: P3) ❌ NOT STARTED

Three separate surfaces report ON while being inert: memory toggles, compression stage
toggles, and `responseValidation`. Operator trust in the UI is currently unfounded.

**Why this priority**: Root cause of the wasted effort in this whole engagement. Prevention,
not repair.

**Acceptance Scenarios**:

1. **Given** a setting displayed as enabled, **When** an operator reads it, **Then** it is
   either genuinely active or visibly marked inert.

---

### Edge Cases

- **All free providers exhausted simultaneously.** `lkgp` falls through to `cc/*` in coding
  and analysis by design; creative/vision/summarization/background have no `cc/*` member and
  will hard-fail instead. This is deliberate — those types must never touch paid quota.
- **Provider recovers mid-session.** `lkgp` promotes on next success; no manual intervention.
- **`tool_result` continuation turns.** Task detection extracts `""` from them
  (`taskAwareRouter.ts:281-291`) and classifies them as `chat`. `task-chat` therefore
  carries a `cc/*` backstop deliberately, because misrouted agentic turns land there.
- **Clearing `activeComboId`.** Would arm `ccr` and `session-dedup`, both of which lose data
  unrecoverably, with `fidelityGate` failing open. See Defect D9.

## Requirements

### Functional Requirements

- **FR-001**: All 7 task types MUST route to a persisted combo, never a bare `auto/*` string.
- **FR-002**: Combo strategy MUST be one of the prompt-cache-affinity-preserving strategies
  (`lkgp`, `priority`, `weighted`, `fill-first` per `promptCacheAffinity.ts:262-264`).
- **FR-003**: `cc/*` MUST appear only in `task-coding`, `task-analysis`, and `task-chat`, and
  MUST be positioned last.
- **FR-004**: Combo members MUST be verified live before deployment, not selected from a
  static catalog.
- **FR-005**: The gateway MUST NOT replay a `thinking` block to a model that did not sign it.
- **FR-006**: A vector-memory write failure MUST surface in logs rather than being swallowed.
- **FR-007**: Task routing MUST be revertible in one call (`task-routing {"enabled":false}`).

### Key Entities

- **Combo**: named target list + strategy + config. `PUT /api/combos/{id}` only.
- **Task routing map**: task type → `combo/<name>`. Global on/off.
- **Compression plan**: resolved from `activeComboId` if set, else derived from engine toggles.
- **Memory settings**: `vectorStore` is a DB setting, not an environment variable.

## Success Criteria

- **SC-001**: All 7 combos report a majority of members healthy. ✅ 24/25.
- **SC-002**: No combo resolves to `cc/*` while any free member is healthy. ✅
- **SC-003**: `thinking`-signature 400s reach zero. ❌ ~1,073/day.
- **SC-004**: Memory retrieval returns `count > 0`. ❌ 227/227 return 0.
- **SC-005**: `cc/*` request share drops against a like-for-like workload. ⏳ unmeasured —
  requires a baseline period on the new config.

## Assumptions

- Free-provider health is volatile; `lkgp` is chosen to adapt rather than to encode a fixed
  ranking. Membership lists will go stale and must be re-verified, not trusted.
- `ghm` (GitHub Models) is the current healthy backbone. It reports no entry under
  `/api/provider-metrics` (which lists `github-models`), so its success rate is **inferred
  from live combo tests, not from metrics**. This is a weaker basis than it appears.
- Per-model tool-calling support is **UNVERIFIABLE** from this gateway: `/api/models` exposes
  no capability field. Agentic suitability of members is assumed, not proven.
- Context-window limits per member are likewise unexposed; overflow behaviour is untested.

## Dependencies

- OmniRoute v3.8.49, global npm install, config at `~/.omniroute/.env`.
- Qdrant 1.19.0 on `localhost:6333` (running, zero collections).
- 9router 0.5.55 on `localhost:20129` isolates Verdict from this gateway.

## Out of Scope

- Auto-registration, trial exploitation, or credential harvesting for new free tiers.
- Re-enabling ToS-prohibited providers (`agy`, `kiro`, `gemini-cli`).
- The gateway's own upstream defects beyond configuration workarounds.
