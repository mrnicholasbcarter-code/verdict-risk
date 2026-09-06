# Feature Specification: Cross-Repository Contract Compatibility

**Feature Branch**: `002-cross-repo-contract-compat`

**Created**: 2026-09-06

**Status**: Draft

**Input**: User description: "Restore honest cross-repository contract compatibility between verdict-risk and current published verdict-core so the fail-closed compatibility gate can pass without weakening it, without a blind consumer-declaration rewrite, and without mixing in the separate security-tooling CI failure. The open README-accuracy change is blocked because the consumer's declared routing-decision contract no longer matches the producer. Decide whether the correct repair is to regenerate the consumer declaration from verified current producer contracts, coordinate a canonical contract release, or change compatibility policy."

## Clarifications

### Session 2026-09-06

- Q: How should the routing-decision contract mismatch be repaired? → A: Regenerate the consumer declaration from verified current producer contracts.
- Q: Where should the compatibility repair ship? → A: New standalone change; leave the open README-accuracy change untouched until this lane is green.
- Q: Are there remaining critical ambiguities after the recorded Q1/Q2 answers? → A: None; proceed to plan. Exact named producer revision at implement time and regeneration mechanics are deferred to planning.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Honest compatibility verdict (Priority: P1)

A maintainer submitting a verdict-risk change needs the required compatibility check to say, truthfully, whether this repository's declared contracts still match the current published producer. If they do not match, the change must stay blocked. If they do match after an approved repair, the check must pass without anyone having to bypass or weaken the gate.

**Why this priority**: The open product change cannot merge while the compatibility gate fails, and a false pass would ship an unverified contract relationship.

**Independent Test**: Run the repository's required compatibility check against the current published producer and confirm it either passes for a verified match or fails closed for a mismatch, with the mismatched contract named.

**Acceptance Scenarios**:

1. **Given** a consumer declaration that no longer matches the current published producer, **When** the required compatibility check runs, **Then** the change is blocked and the mismatched contract is identified.
2. **Given** an approved repair that makes the consumer declaration match the current published producer, **When** the required compatibility check runs, **Then** the check passes without any waiver or fail-open exception.
3. **Given** a proposed repair that only edits the declaration without verified producer evidence, **When** reviewers inspect the change, **Then** that repair is rejected.

---

### User Story 2 - Choose an evidence-backed repair path (Priority: P1)

A coordinator deciding how to unblock compatibility needs an explicit, recorded choice among: regenerate the consumer declaration from verified current producer contracts; coordinate a canonical contract release on the producer side; or change the compatibility policy. The choice must name the contract owner, the affected repositories, and the ordered rollout.

**Why this priority**: The constitution forbids starting dependent changes while ownership, compatibility policy, and rollout order are unknown. Guessing a declaration-only fix is explicitly out of bounds.

**Independent Test**: A reviewer can read the recorded decision and point to the chosen path, the owning repository, and the rollout/rollback order without inferring them from code.

**Acceptance Scenarios**:

1. **Given** the current mismatch on the routing-decision contract, **When** the repair path is selected, **Then** exactly one of the allowed paths is recorded and the others are rejected with a reason.
2. **Given** a selected path, **When** implementation is later planned, **Then** the producer remains the owner of contract meaning and the consumer remains the owner of its declaration unless the recorded decision explicitly transfers that ownership.
3. **Given** the selected path, **When** rollout is described, **Then** it states which repository changes first, what evidence must exist before the dependent repository changes, and how to roll back if the gate still fails.

---

### User Story 3 - Keep unrelated product work and security-tooling work separate (Priority: P2)

A reviewer looking at this compatibility repair must be able to tell it apart from the already-implemented README-accuracy/feature-reconciliation work and from the separate security-tooling CI failure. This feature must not absorb those lanes or weaken their gates in order to look green.

**Why this priority**: Mixing blockers hides cause, invites gate-weakening, and makes merge authorization unsafe.

**Independent Test**: Inspect the compatibility change set and confirm it does not rewrite the product-feature behavior and does not treat the security-tooling failure as in-scope unless a later decision explicitly says otherwise.

**Acceptance Scenarios**:

1. **Given** the open README-accuracy change, **When** this compatibility feature is delivered, **Then** it ships as a new standalone change and does not edit or fold into that open product change.
2. **Given** the existing security-tooling CI failure on the same open change, **When** this compatibility feature is delivered, **Then** that failure remains a separate lane and is not marked resolved by this work.
3. **Given** a compatibility repair that would also silence the security-tooling failure by weakening that gate, **When** reviewers inspect the change, **Then** that repair is rejected.

---

### Edge Cases

- The mismatch already existed on the producer before the current product change; the consumer declaration is stale relative to the producer, not evidence that the product change altered the producer contract.
- More than one declared contract could mismatch later; the first repair must not assume the routing-decision contract is the only possible mismatch.
- The producer default branch can move while this feature is in progress; a repair is valid only against a named producer revision, not an unnamed moving target.
- A consumer declaration that matches an older producer revision must still fail against the current published producer.
- If evidence needed to choose a repair path cannot be obtained, the result is blocked/unknown rather than guessed.
- Rollback must restore a fail-closed blocked state rather than a waived pass.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The required compatibility check MUST remain fail-closed. A mismatch MUST block the change. The check MUST NOT be skipped, weakened, or treated as optional to obtain a pass.
- **FR-002**: When the check blocks, it MUST identify the mismatched contract by name. The current verified mismatch is the routing-decision contract; the feature MUST still handle the general case of one or more mismatched contracts.
- **FR-003**: A consumer declaration MUST be accepted only when it matches the current published producer for every declared contract, based on verified producer evidence for a named producer revision.
- **FR-004**: The feature MUST regenerate the consumer declaration from verified current producer contracts for a named producer revision. It MUST NOT treat a canonical producer release or a compatibility-policy change as the repair path for this lane.
- **FR-005**: A declaration-only edit without verified producer evidence MUST be rejected.
- **FR-006**: Cross-repository work MUST name the contract owner, the consumer-declaration owner, compatibility requirements, validation in each affected repository, and an ordered rollout and rollback path before the first dependent change is merged.
- **FR-007**: This feature MUST NOT treat the separate security-tooling CI failure as in scope. That failure MUST remain a distinct lane.
- **FR-008**: This feature MUST NOT rewrite or re-implement the README-accuracy/feature-reconciliation product work. That work stays owned by its existing change.
- **FR-009**: Completion claims MUST bind to an exact consumer source state, the named producer revision used for comparison, the required check outcomes, and any remaining failed or unavailable checks. Unknown results MUST be reported as unknown, not as passing.
- **FR-010**: After the approved repair, reviewers MUST be able to determine within one review whether the shipped path regenerated consumer evidence, released a canonical producer contract, or changed policy.
- **FR-011**: The open README-accuracy change MUST NOT be merged until this compatibility feature has an approved spec path, implementation, tests, and green required compatibility checks, and any remaining required failures are owned by their own approved lanes.

### Key Entities

- **Producer contract**: The meaning of a shared interface published by the owning producer repository. The producer owns that meaning.
- **Consumer declaration**: The consumer repository's recorded claim about which producer contracts it is compatible with.
- **Compatibility verdict**: The fail-closed result of comparing the consumer declaration to the current published producer: allowed, or blocked with named mismatches.
- **Named producer revision**: The exact producer source identity used for comparison. A moving default branch is not by itself a named revision.
- **Repair path**: The recorded choice among regenerating the consumer declaration from verified producer evidence, coordinating a canonical producer release, or changing compatibility policy.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of required compatibility checks on the repaired consumer change conclude with either an honest pass or an explained residual block. No required check is skipped or waived to create a pass.
- **SC-002**: A mismatched consumer declaration is rejected 100% of the time; no mismatched declaration is accepted as compatible.
- **SC-003**: Reviewers can identify the recorded repair path, contract owner, and rollout order in a single review pass, without inferring them from informal notes.
- **SC-004**: The separate security-tooling failure remains unresolved by this feature; it is not counted as success for this lane.
- **SC-005**: The open product change remains unmerged until this compatibility lane and any other required remaining blockers each have their own approved path and passing required checks.

## Assumptions

- The workspace constitution (v1.1.0) governs this work. Child-repository rules may be stricter but cannot weaken fail-closed compatibility, repository boundaries, or evidence requirements.
- Live verification on 2026-09-06 confirmed the open README-accuracy change is still blocked by a routing-decision contract mismatch against producer revision `536c79e`, plus a separate security-tooling failure. There are no review approvals, and the change is not mergeable. That product change must not be merged in this specify step.
- The routing-decision contract mismatch predates the recent producer setup-DX merge. It is not evidence that the README-accuracy change altered the producer contract. It is evidence that the consumer declaration is stale relative to the current published producer.
- This feature owns compatibility repair only. The security-tooling / setuptools failure is a later, separate Spec Kit lane.
- Isolated worktrees and one writer per worktree remain mandatory. The dirty verdict-risk and verdict-node main checkouts, and the existing README-accuracy worktree, are not writers for this feature.
- GitHub issues, task checkboxes, and handoff files are leads. Live repository source, GitHub, and check runs are authoritative.
- Recorded answers on 2026-09-06: Q1 = regenerate the consumer declaration from verified producer evidence; Q2 = new standalone change, do not edit the open README-accuracy change. Clarify completed the same day with no remaining critical ambiguities; next command is `/speckit-plan`.
