# Implementation Plan: OmniRoute Gateway Remediation

**Branch**: `001-omniroute-gateway-remediation` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification and [defects.md](./defects.md)

## Summary

Conserve paid `cc/claude-*` quota by routing routine work to live-verified free providers,
and eliminate the gateway's ongoing hard-failure bleed. US1 is delivered. The remaining work
is dominated by two upstream translation defects (D1, D2) that together account for ~1,777
hard failures per day and are unrelated to routing configuration.

## Technical Context

**Runtime**: OmniRoute v3.8.49, global npm install at
`/home/nick/.nvm/versions/node/v24.19.0/lib/node_modules/omniroute`
**Gateway**: `http://localhost:20128` — dedicated to Claude Code feature-building
**Isolation**: 9router 0.5.55 on `:20129` serves Verdict, keeping it off this gateway
**Storage**: `~/.omniroute/storage.sqlite`; config `~/.omniroute/.env`
**Vector store**: Qdrant 1.19.0 on `:6333` — running, zero collections
**Primary dependency**: free-provider availability, which is volatile and outside our control

**Configuration surface** (all changes are API/DB-level; no source patching):
- `PUT /api/combos/{id}` — membership and strategy. PATCH is 405.
- `PUT /api/settings/task-routing` — task type → combo map, global on/off
- `PATCH /api/settings` — global settings
- `POST /api/combos/test` — live member health; result field is `status`, not `success`

## Constitution Check

| Principle | Status |
|---|---|
| Read the docs before touching a library | **Enforced.** Every finding cites installed source, live API, or DB. Four fabricated env vars were caught by grepping the package rather than trusting a plausible suggestion. |
| Report findings with evidence; let the user decide | **Enforced.** Adversarial reviews were prompted to refute; UNVERIFIABLE is recorded as such rather than assumed working. |
| Do what has been asked, nothing more | **Enforced.** US2–US5 are specified but deliberately unimplemented pending direction. |
| Never claim unverified success | **Enforced.** SC-005 (`cc/*` share drop) is marked unmeasured; `ghm` health is marked inferred. |
| Ask before destructive actions | **Applies to US3/US5** — both touch persisted settings; US3 additionally requires a Qdrant collection create. |

**Deviation recorded**: US1 was implemented before this spec existed, contrary to the
spec-kit phase order. This document is retrospective for that story. The cost of that
inversion is visible in D3 — combo members were selected without a health precondition,
which a written plan would have required.

## Project Structure

### Documentation (this feature)

```
.specify/specs/001-omniroute-gateway-remediation/
├── spec.md        # user stories, requirements, success criteria
├── defects.md     # evidence register D1–D13, cited to file:line
├── plan.md        # this file
└── tasks.md       # phased task breakdown
```

### Configuration under change

```
~/.omniroute/
├── .env                 # D13: four fabricated OMNIROUTE_* vars to remove
└── storage.sqlite       # combos, settings, memory tables (via API, not direct writes)
```

No application source is modified. D1, D2, D8, D11 and D12 are upstream code defects; this
plan addresses them by configuration avoidance and documents the code-level fix direction for
whoever owns the package.

## Phasing Rationale

Ordered by **measured daily loss**, not by conceptual tidiness:

1. **US1 routing** (done) — was actively regressing; 0% combo success.
2. **US2 / D1** — 1,073 failures/day, pure loss, no tradeoff, fully independent.
3. **D2** — 704 failures/day, same translation layer as D1.
4. **US3 memory** — high value but currently inert rather than harmful. Requires all four
   blockers (D4–D7) in one change; partial fixes are unobservable.
5. **US4 / US5** — small, safe, optional.

## Risk Register

| Risk | Mitigation |
|---|---|
| Clearing `activeComboId` to "fix" dead compression toggles arms two lossy engines with fidelityGate failing open (D9) | Recorded in memory and defects.md as load-bearing. Disable `ccr` + `session-dedup` first. |
| Free-provider membership goes stale; combos silently degrade | Health precondition on every membership change; `lkgp` adapts automatically to per-provider failure. |
| Fixing one memory blocker and concluding memory works | D4–D7 must ship together; acceptance is `count > 0` on retrieval, not "setting applied". |
| Re-adding `mistral`/`cerebras` when credits reset, forgetting cerebras' unfixed `reasoning_content` defect | Recorded in defects.md; cerebras needs the `default.ts:607` mistral-scoped strip generalised first. |
| Combo members lack tool-calling support (UNVERIFIABLE) | Accepted risk. Detectable only through live agentic failure; `lkgp` fails over on error. |

## Complexity Tracking

No constitutional violations requiring justification. The one structural compromise is that
US1 shipped ahead of its specification; this is recorded above rather than retro-justified.
