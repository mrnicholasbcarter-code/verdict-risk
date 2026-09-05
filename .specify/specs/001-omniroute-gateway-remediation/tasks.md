# Tasks: OmniRoute Gateway Remediation

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [defects.md](./defects.md)
**Organization**: by user story, ordered by measured daily loss.

## Format: `[ID] [P?] [Story] Description`
- `[P]` = parallelisable (different surface, no shared state)
- Story tag maps the task to its user story for independent delivery

## Path Conventions

`$PKG` = `/home/nick/.nvm/versions/node/v24.19.0/lib/node_modules/omniroute`
`$GW` = `http://localhost:20128`
Config changes go through the API. No direct `storage.sqlite` writes.

---

## Phase 1: Setup ✅ COMPLETE

- [X] T001 Isolate Verdict onto 9router `:20129` so this gateway serves only Claude Code
- [X] T002 Remove claude-flow / ruflo hooks from `.claude/settings.json`
- [X] T003 Establish evidence baseline: provider metrics, combo membership, live model catalog

---

## Phase 2: Foundational ✅ COMPLETE

- [X] T004 Confirm combo write contract: `PUT /api/combos/{id}` only (PATCH 405, POST → COMBO_004)
- [X] T005 Confirm combo test contract: result field is `status:"ok"`, **not** `success`
- [X] T006 Read strategy implementations; identify prompt-cache-affinity allowlist at
      `$PKG/open-sse/services/combo/promptCacheAffinity.ts:262-264`

---

## Phase 3: User Story 1 — Route routine work to free providers (P1) ✅ DELIVERED

**Goal**: All 7 task types resolve to healthy free models; `cc/*` genuinely last resort.
**Independent test**: `POST $GW/api/combos/test` per type → majority `status:"ok"`,
`resolvedBy` names a free model.

- [X] T007 [US1] Rank providers by live health via `GET /api/provider-metrics` and
      `GET /api/providers` (`testStatus`)
- [X] T008 [US1] Enumerate real model ids via `GET /api/models`; confirm the double vendor
      segment `nvidia/nvidia/...` is correct, not a typo
- [X] T009 [US1] Replace `round-robin` with `lkgp` on all 7 combos (D3)
- [X] T010 [US1] Rebuild membership from live-verified providers; drop `mistral/*` and
      `cerebras/*` (both `credits_exhausted` 402)
- [X] T011 [US1] Position `cc/claude-opus-5` last in `task-coding`, `task-analysis`,
      `task-chat`; absent from the other four
- [X] T012 [US1] Live-test all 7 combos → 24/25 members healthy, all resolving to `ghm/*`
- [X] T013 [US1] Drop `nvidia/qwen/qwen3.5-397b-a17b` from `task-coding` (20s timeout)
- [X] T014 [US1] Enable task routing for all 7 types
- [X] T015 [US1] Record findings and landmines in auto-memory

**Checkpoint**: SC-001 ✅, SC-002 ✅. SC-005 (`cc/*` share drop) **unmeasured** — see T016.

- [ ] T016 [US1] Establish a like-for-like baseline over a normal working day and measure
      `cc/*` request-share delta on `/dashboard/costs`. Until this runs, the quota-conservation
      claim is **unproven**, not proven.

---

## Phase 4: User Story 2 — Stop the thinking-signature bleed (P1) ❌ NOT STARTED

**Goal**: zero `Invalid \`signature\` in \`thinking\` block` errors.
**Independent test**: force a failover in `auto/best-reasoning`; assert the second outbound
body carries no foreign-signed `thinking` block.
**Scale**: ~1,073 failures/day. Largest single loss on the gateway.

- [ ] T017 [US2] Reproduce deterministically: capture a call-log pair showing a `thinking`
      block signed by model A replayed to model B
- [ ] T018 [US2] Decide remedy — (a) strip `thinking` on model switch, or (b) pin
      `auto/best-reasoning` to a single model. (a) preserves the combo's purpose; (b) is
      config-only and available immediately. **Requires Nick's decision.**
- [ ] T019 [P] [US2] If (a): generalise the `reasoning_content` strip at
      `$PKG/open-sse/executors/default.ts:601-628` beyond its `provider === "mistral"` gate
      (line 607) to cover cross-model replay. Note this is a **package source change** —
      it will be lost on upgrade unless carried upstream.
- [ ] T020 [P] [US2] If (b): rewrite `auto/best-reasoning` membership to a single model
- [ ] T021 [US2] Verify over 24h: thinking-signature 400 count reaches zero (SC-003)

---

## Phase 5: Defect D2 — claude→gemini translator (P1) ❌ NOT STARTED

**Goal**: eliminate 704 `Expected input to contain field: 'messages'` errors/day.

- [ ] T022 Analyse the sample call log
      `~/.omniroute/call_logs/2026-08-25/2026-08-25T09-15-52.311Z_1787649345240-c90fb1.json`
      and locate the translation site emitting a body with neither `messages` nor `contents`
- [ ] T023 [P] Determine whether any combo can avoid `claude→gemini` entirely (config-level
      workaround) versus requiring a source fix
- [ ] T024 [P] Address the two relatives on the same path: `Unknown name "encrypted" at
      'tools[0].function_declarations[3]'` (85/day) and `thinking: property 'thinking' is
      unsupported` (33/day)

---

## Phase 6: User Story 3 — Make memory function (P2) ❌ NOT STARTED

**Goal**: retrieval returns `count > 0` and injected bodies carry retrieved text.
**Independent test**: converse, then assert a non-zero Qdrant point count and a retrieval
with `count > 0`.

⚠️ **D4–D7 are each independently fatal. Ship them together — a partial fix produces no
observable change and will read as "still broken".**

- [ ] T025 [US3] Set `qdrantHost` to `localhost` (D4). Confirm the five guards at
      `$PKG/src/lib/memory/qdrant.ts:185,284,353,413,443` now pass
- [ ] T026 [US3] Select a real embedder (D5): set `memoryEmbeddingProviderModel`, **or**
      enable `staticEnabled`/`transformersEnabled`. `embeddingSource=auto` with all three
      unset resolves to nothing, silently
- [ ] T027 [US3] Fix `qdrantEmbeddingModel` (D6): choose a valid id from the openrouter list
      at `$PKG/open-sse/config/embeddingRegistry.ts:203-243`, **or** switch the provider to
      `gemini`. Current value is cross-wired
- [ ] T028 [US3] Align `QDRANT_VECTOR_SIZE` with the chosen embedder's dimension (D6 latent —
      default is 1536; `gemini-embedding-2` emits 768)
- [ ] T029 [US3] Confirm collection creation: `GET localhost:6333/collections` must list a
      non-empty result. **Creates persistent state — confirm with Nick first.**
- [ ] T030 [US3] Address extraction (D7): regex extraction yielded 1 artifact row from 268
      attempts. Determine whether an LLM-based extraction path exists or whether memory is
      viable at all without one
- [ ] T031 [US3] Verify SC-004 end-to-end: converse → store → retrieve `count > 0` → injected
- [ ] T032 [P] [US3] Raise visibility on silent failure (D8): upserts at
      `$PKG/src/lib/memory/store.ts:232,298` are fire-and-forget. At minimum, confirm that
      once configured, `qdrant.upsert.*` lines actually appear — their total absence was the
      reason this went unnoticed for weeks

---

## Phase 7: Defect D12 — task detection misroutes agentic turns (P2) ❌ NOT STARTED

- [ ] T033 Confirm the `tool_result` → empty `userText` path at
      `$PKG/open-sse/services/taskAwareRouter.ts:281-291` against live call logs
- [ ] T034 Decide whether the unconditional pin-override (empty `if` guard at `:371-376`,
      live `detected:88 / routed:88`) is acceptable. It contradicts the workspace's
      "client pins, gateway routes" design. **Requires Nick's decision.**
- [ ] T035 Keep `cc/*` in `task-chat` while D12 stands — misrouted agentic turns land there

---

## Phase 8: User Stories 4 & 5 — Compression and legibility (P3) ❌ NOT STARTED

- [ ] T036 [P] [US4] Disable `caveman`: reverts its own output 74.7% of the time for 0.14%
      of token savings, applied at `ultra` to the user's literal typed prompts
- [ ] T037 [P] [US4] Consider raising `rtk`'s `maxLinesPerResult:120` — it deletes tool output
      aggressively (one recorded run: 620,908 → 195,185 tokens)
- [ ] T038 [US4] Set `fidelityGate.enabled = true` before **any** pipeline change — it is
      absent from config, so `fidelityGateStep.ts:27` fails open
- [ ] T039 [P] [US5] Remove the four fabricated `OMNIROUTE_*` vars from `~/.omniroute/.env`
      (D13). `OMNIROUTE_QDRANT_URL` actively masks D4 by appearing to configure the host
- [ ] T040 [US5] Document the three lying surfaces (memory toggles, compression toggles,
      `responseValidation`) wherever an operator will next look

---

## Dependencies & Execution Order

### Phase dependencies
- Phase 1–2 → Phase 3 (complete)
- Phases 4, 5, 6, 7, 8 are **mutually independent** and may run in any order
- Within Phase 6, T025–T028 must land together before T029/T031 can pass

### Blocking decisions (Nick)
- **T018** — strip `thinking` on switch vs. pin the combo to one model
- **T029** — creating a persistent Qdrant collection
- **T034** — whether 100% pin-override is acceptable

### Parallel opportunities
- T019/T020, T023/T024, T036/T037/T039 are independent surfaces
- Phase 4 and Phase 6 touch entirely different subsystems and may proceed concurrently

---

## Recommended MVP

**Phase 4 alone.** It removes ~1,073 hard failures/day, is fully independent of every other
phase, and option (b) at T020 is a config-only change available immediately.

Phase 6 is the highest-value *capability* work, but it is inert-not-harmful today and needs
four coordinated changes plus a decision on whether regex extraction makes memory viable at
all.
