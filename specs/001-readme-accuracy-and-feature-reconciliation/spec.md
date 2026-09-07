# Feature Specification: README Accuracy and Feature Reconciliation

**Feature Branch**: `001-readme-accuracy-and-feature-reconciliation`

**Created**: 2026-09-05

**Status**: Awaiting owner decisions (see Open decisions section below)

**Input**: Fix broken org links and reconcile three documented-but-absent features in the
verdict-risk README: Correlation Gate, Kelly Sizing, and YAML-driven desk controls.

---

## Clarifications

### Session 2026-09-05

- Q: Ambiguity scan performed by risk-spec agent. Three open decisions (Q1/Q2/Q3) identified
  and documented below. No additional hidden ambiguities found beyond these three. The
  unconditional scope (FR-001/FR-002: link fixes) is fully specified and may be tasked and
  implemented without owner input.
- Q1/Q2/Q3 status: OPEN — owner answers required before implementation tasks can be generated
  for gated features. See "Open decisions for owner" section.

---

## Owner decisions (resolved 2026-09-05)

Three features are documented in the README but are absent from the code. Each has a real
implementation in `~/kalshi-trader`. The owner must choose a disposition for each before
implementation can proceed.

### Q1 — Correlation Gate

**Context**: README claims a pairwise correlation matrix gate (`max_correlation: 0.7`,
`lookback_window: 100`). The actual gate in verdict-risk (`evaluate_concentration`) is a
family-exposure bucket check — not pairwise correlation. The kalshi-trader has a proven
cluster/expiry exposure cap in `v40/risk.py:282-354`.

**Options**:

| Option | Answer | Implications |
|--------|--------|--------------|
| A | Port cluster/expiry exposure cap from kalshi-trader v40/risk.py | Proven in production; different from README description; update README to match |
| B | Build a true pairwise correlation matrix gate matching README exactly | New feature; needs `lookback_window` of price series; significant new scope |
| C | Mark as roadmap; remove from feature table in README | No code change; README becomes accurate |

**Owner decision**: A — port cluster/expiry exposure cap from kalshi-trader v40/risk.py; README reworded to match (decided by owner 2026-09-05)

---

### Q2 — Kelly Sizing

**Context**: README claims a Kelly gate (`conservative_fraction: 0.5`). No Kelly function
exists in verdict-risk. The kalshi-trader has a working half-Kelly implementation at
`v40/portfolio/kelly.py:17-67` (`_per_trade_kelly_fraction`, `portfolio_kelly_sizes`).

**Options**:

| Option | Answer | Implications |
|--------|--------|--------------|
| A | Port v40/portfolio/kelly.py into verdict-risk as a new sizing function | Small, self-contained port (~67 lines); adds `kelly_fraction` param to RiskContext or a new sizer class |
| B | Reference kalshi-trader as canonical source; README links only, no code copy | No implementation; README describes it as "available in kalshi-trader" |
| C | Mark as roadmap; remove Kelly from feature table and YAML config block | No code change; README becomes accurate |

**Owner decision**: A — port v40/portfolio/kelly.py into verdict-risk with tests (decided by owner 2026-09-05)

---

### Q3 — YAML desk controls

**Context**: README shows a `~/.verdict/risk_config.yaml` config file driving all parameters.
No YAML loading code exists in verdict-risk — parameters are passed as Python constructor
arguments. The kalshi-trader v50 config (`v50/config.yaml`) is a fully YAML-driven desk
control system loaded in `v50/runner.py:365`.

**Options**:

| Option | Answer | Implications |
|--------|--------|--------------|
| A | Implement a YAML loader for RiskContext / RiskAuthority driven by README schema | New module; adds pyyaml dep; needs validation, tests; owner chooses config path |
| B | Document that parameters are code-injected only; remove YAML block from README | No code change; README becomes accurate |
| C | Add stub schema file (YAML template only, no loader) with roadmap note | Config file ships as example; loading is a future task |

**Owner decision**: A — build loader for ~/.verdict/risk_config.yaml via yaml.safe_load, add pyyaml dependency (decided by owner 2026-09-05)

---

## User Scenarios and Testing

### User Story 1 — Accurate Repository Links (Priority: P1)

A developer reading the README clicks any of the three `github.com/verdict/*` links and
reaches the correct repository, not a 404.

**Why this priority**: Broken links are immediately visible to every reader; they erode
credibility and block navigation. Fix is mechanical and risk-free.

**Independent Test**: Load README in a browser; every internal link resolves with HTTP 200.

**Acceptance Scenarios**:

1. **Given** the README on the default branch, **When** a reader clicks the verdict-core
   link, **Then** the browser opens `https://github.com/mrnicholasbcarter-code/verdict-core`
   (or the repo's canonical URL) and returns HTTP 200.
2. **Given** the README, **When** all three `verdict/*` links are audited, **Then** every
   URL resolves without a 404 or redirect to a non-existent page.
3. **Given** verdict-edge does not exist as a repo, **When** the link fix is applied,
   **Then** the verdict-edge entry is either removed or replaced with a roadmap note — it
   is not replaced with a broken URL.

---

### User Story 2 — Feature Table Reflects Reality (Priority: P1)

A developer reading the README's feature table and YAML config block finds that every entry
matches something that actually exists (or is clearly marked as roadmap).

**Why this priority**: The README is the contract between this library and its users. Listing
Correlation Gate and Kelly Sizing as current features when they are absent constitutes false
advertising and leads to integration failures.

**Independent Test**: For each feature row, a reader can find a corresponding function/class
in `src/trade_risk_engine/` or a GitHub issue tracking it as roadmap.

**Acceptance Scenarios**:

1. **Given** a Correlation Gate entry in the feature table, **When** a developer searches
   the package source for `correlation`, **Then** they find either a real implementation or
   a clear note pointing to the chosen disposition (ported, external ref, or roadmap).
2. **Given** a Kelly Sizing entry, **When** a developer imports from `trade_risk_engine`,
   **Then** they either find a Kelly function or see a README note that correctly describes
   its status.
3. **Given** the YAML config block in README, **When** a developer copies it to
   `~/.verdict/risk_config.yaml`, **Then** the README explains clearly whether that file is
   loaded by the library (and how) or whether it is purely illustrative.

---

### User Story 3 — Correlation Gate Implementation Delivered (Priority: P2, Owner Decision Q1 required)

*This story activates only if the owner chooses option A or B for Q1.*

A developer instantiates a `RiskAuthority` with a correlation limit and the gate fires
when the proposed trade would exceed it.

**Acceptance Scenarios**:

1. **Given** a cluster exposure limit and existing open positions in the same cluster,
   **When** `evaluate_trade` is called, **Then** the decision is rejected with
   `ERR_CORRELATION_CAP`.
2. **Given** the same scenario with the proposed trade below the cap, **Then** the
   decision is approved.
3. **Given** unit tests covering the gate, **When** `pytest` runs, **Then** all tests pass.

---

### User Story 4 — Kelly Sizing Delivered (Priority: P2, Owner Decision Q2 required)

*This story activates only if the owner chooses option A for Q2.*

A developer calls a Kelly sizing function with win probability and price, and receives a
position size calibrated to the fractional Kelly formula.

**Acceptance Scenarios**:

1. **Given** `p_win=0.6`, `price=0.5`, `kelly_fraction=0.25`, **When** the Kelly function
   is called, **Then** the returned fraction matches `((0.6*1 - 0.4) / 1) * 0.25`.
2. **Given** `p_win <= price` (negative edge), **Then** the function returns 0.0.
3. **Given** the function is called with invalid float inputs (NaN/inf), **Then** it returns
   0.0 without raising.

---

### User Story 5 — YAML Config Loader Delivered (Priority: P3, Owner Decision Q3 required)

*This story activates only if the owner chooses option A for Q3.*

A developer creates `~/.verdict/risk_config.yaml` and the library reads it to populate
`RiskContext` and `RiskAuthority` parameters.

**Acceptance Scenarios**:

1. **Given** a valid YAML file at the configured path, **When** the loader is called,
   **Then** `RiskContext` fields match the YAML values.
2. **Given** a missing or unreadable config file, **Then** the loader raises a descriptive
   error rather than silently using defaults.
3. **Given** an invalid YAML value for a numeric field, **Then** the loader raises a
   descriptive validation error.

---

### Edge Cases

- verdict-edge repo: may not exist under `mrnicholasbcarter-code`; link fix must not
  produce a second broken URL.
- Negative Kelly edge: `p_win * b - p_loss <= 0` must return 0.0, not a negative size.
- Cluster map exhaustion: a ticker not in `COIN_CLUSTERS` must be handled without crashing.
- YAML schema additions: adding new fields to RiskContext must not silently break the loader.

---

## Requirements

### Functional Requirements

- **FR-001**: README MUST fix all three broken `github.com/verdict/*` links to their correct
  destinations.
- **FR-002**: README MUST NOT contain a link to a repository that does not exist.
- **FR-003**: Every feature listed in the README feature table MUST correspond to either
  (a) an importable function/class in `trade_risk_engine`, or (b) a clearly marked roadmap
  entry with a tracking issue.
- **FR-004**: The YAML config block in README MUST accurately describe whether it is
  operational or illustrative, based on owner decision Q3.
- **FR-005**: The performance benchmark table MUST only cite numbers producible by the
  included benchmark (`trade_risk_engine.benchmark`) on the features that exist.
- **FR-006**: The mathematical properties table MUST only list properties that have
  corresponding test coverage in the test suite.
- **FR-007** *(if Q1 = A)*: A correlation/cluster-cap gate MUST be implemented with its
  own unit tests.
- **FR-008** *(if Q2 = A)*: A Kelly sizing function MUST be implemented with tests covering
  positive edge, zero edge, and invalid float inputs.
- **FR-009** *(if Q3 = A)*: A YAML config loader MUST be implemented with tests covering
  valid config, missing file, and invalid field values.

### Key Entities

- **RiskContext**: Immutable parameter set for a stateless evaluation; gains new fields only
  when a feature is ported.
- **RiskAuthority**: Coordinator; gains new gate wiring when a feature is ported.
- **README feature table**: Source-of-truth for documented feature claims.
- **Benchmark module**: Source-of-truth for latency numbers.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: Zero HTTP 404s when following any link in the README (verifiable by curl or
  browser).
- **SC-002**: Every row in the README feature table has a matching symbol in
  `trade_risk_engine` or a tracking issue labelled `roadmap`.
- **SC-003**: The README YAML config block is labelled either "operational" or "illustrative"
  per owner decision Q3.
- **SC-004** *(if Q1 = A)*: Correlation gate unit tests pass with 100% branch coverage of
  the new gate function.
- **SC-005** *(if Q2 = A)*: Kelly sizing tests cover positive, zero-edge, and NaN/inf cases
  and all pass.
- **SC-006** *(if Q3 = A)*: YAML loader tests cover happy path, missing file, and validation
  error cases and all pass.
- **SC-007**: Existing test suite (`pytest tests/`) continues to pass with no regressions
  after any change.

---

## Assumptions

- The real GitHub org is `mrnicholasbcarter-code`; this was confirmed by the prior audit.
- `verdict-edge` does not exist as a public repo; its link will be removed or replaced with
  a roadmap note rather than corrected to a different URL.
- The two `ruvnet/*` external links are out of scope; they may be correct and are not
  owned by this project.
- Owner decisions Q1/Q2/Q3 resolved 2026-09-05: all option A (port). Tasks T016–T040 and
  issues #30–#32 are therefore active, not conditional. Link fix (FR-001, FR-002) is
  unconditional.
- Port scope for Q2 option A is minimal: `_per_trade_kelly_fraction` + `portfolio_kelly_sizes`
  (~67 lines), no new dependency beyond the standard library.
